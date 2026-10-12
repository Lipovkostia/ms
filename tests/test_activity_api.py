"""Regression for Streamlit workers retaining the original API allowlist."""
from datetime import date
import unittest
from unittest.mock import patch
import pandas as pd
from sales_center.activity_api import ClientActivityClient, load_client_activity, register_activity_entities
from sales_center.live_data import local_id
from sales_center.moysklad import MoySkladClient, MoySkladError

OLD_ENTITIES={'counterparty','assortment','demand','currency'}


class ActivityApiTests(unittest.TestCase):
    def collections(self):
        return {
            'counterparty':[{'id':'c','owner':{'id':'e'}}],
            'employee':[{'id':'e','name':'Анна'}],
            'currency':[{'id':'rub','isoCode':'643'}],
            'demand':[{'id':'s','applicable':True,'agent':{'id':'c'},'moment':'2026-10-10 12:00:00','sum':10000,'rate':{'currency':{'id':'rub'}}}],
            'customerorder':[{'id':'o','agent':{'id':'c'},'created':'2026-10-11 12:00:00'}],
        }

    def test_load_with_old_cached_base_allowlist_and_session_cleanup(self):
        clients=pd.DataFrame([{'client_id':local_id('c'),'company':'Клиент'}])
        source=self.collections()
        paths=[]
        def response(api,path,params,session=None):
            paths.append(path)
            rows=[] if params.get('filter')=='archived=true' else source[path.split('/')[-1]]
            return {'rows':rows,'meta':{'size':len(rows)}}
        with patch.object(MoySkladClient,'ENTITIES',OLD_ENTITIES),patch.object(ClientActivityClient,'_get',response),patch('requests.Session.close') as close:
            result=load_client_activity('test-only',clients,date(2026,10,12))
            close.assert_called_once()
        self.assertIn('entity/employee',paths)
        self.assertIn('entity/customerorder',paths)
        self.assertEqual(result.iloc[0].owner_employee,'Анна')
        self.assertEqual(result.iloc[0].purchase_history[0]['amount'],100)
        self.assertEqual(len(result.iloc[0].recent_order_dates),1)
        self.assertNotIn('purchase_history',clients.columns)

    def test_cached_loader_references_are_upgraded_without_replacing_error_class(self):
        cached_factory=MoySkladClient
        cached_error=MoySkladError
        with patch.object(MoySkladClient,'ENTITIES',OLD_ENTITIES):
            register_activity_entities()
            self.assertIs(cached_factory,MoySkladClient)
            self.assertIs(cached_error,MoySkladError)
            api=cached_factory('test-only')
            try:
                with patch.object(api,'_all',return_value=[]) as read:
                    self.assertEqual(api.list_entities('employee'),[])
                    self.assertEqual(api.list_entities('customerorder'),[])
                    self.assertEqual(read.call_count,2)
                    with self.assertRaises(ValueError): api.list_entities('organization')
                    self.assertEqual(read.call_count,2)
            finally: api.session.close()

    def test_full_refresh_uses_cached_base_reference_after_bridge(self):
        from sales_center.sync import refresh
        source=self.collections()
        source['counterparty'][0].update(name='Клиент',accountId='test-account')
        source['assortment']=[{'id':'p','name':'Сыр','pathName':'Сыры'}]
        doc=source['demand'][0]
        doc['positions']={'meta':{'size':1},'rows':[{'assortment':source['assortment'][0],'quantity':1,'price':10000}]}
        reads=[]
        def response(api,path,params,session=None):
            reads.append(path)
            rows=source[path.split('/')[-1]]
            return {'rows':rows,'meta':{'size':len(rows)}}
        state={}
        with patch.object(MoySkladClient,'ENTITIES',OLD_ENTITIES),patch('sales_center.live_data.MoySkladClient',MoySkladClient),patch.object(MoySkladClient,'_get',response):
            register_activity_entities()
            frames=refresh(state,date(2026,10,12),token='test-only',retain=True)
        self.assertIn('entity/employee',reads)
        self.assertIn('entity/customerorder',reads)
        self.assertTrue(frames[0].iloc[0].crm_history_loaded)
        self.assertEqual(frames[0].iloc[0].owner_employee,'Анна')
        self.assertIn('live_analytics',state)

    def test_unknown_paths_are_rejected_before_http(self):
        api=ClientActivityClient('test-only')
        try:
            with patch.object(api,'_get') as get:
                for entity in ['../employee','employee/../organization','organization','https://example.com']:
                    with self.assertRaises(ValueError): api.list_entities(entity)
                get.assert_not_called()
        finally: api.session.close()

    def test_employees_use_inherited_pagination(self):
        api=ClientActivityClient('test-only')
        try:
            with patch.object(MoySkladClient,'ENTITIES',OLD_ENTITIES),patch.object(api,'_get',side_effect=[{'rows':[{'id':str(i)} for i in range(1000)],'meta':{'size':1001}},{'rows':[{'id':'1000'}],'meta':{'size':1001}}]) as get:
                rows=api.list_entities('employee')
                self.assertEqual(len(rows),1001)
                self.assertEqual(get.call_args_list[1].args[1]['offset'],1000)
        finally: api.session.close()

    def test_malformed_api_collection_has_sanitized_error_and_closes_session(self):
        clients=pd.DataFrame([{'client_id':local_id('c'),'company':'Клиент'}])
        source=self.collections()
        source['demand'][0]['moment']='private response'
        def response(api,entity,params=None,progress=None):
            return [] if params and params.get('filter')=='archived=true' else source[entity]
        with patch.object(ClientActivityClient,'list_entities',response),patch('requests.Session.close') as close:
            with self.assertRaises(MoySkladError) as error:
                load_client_activity('test-only',clients,date(2026,10,12))
            close.assert_called_once()
        self.assertNotIn('private response',str(error.exception))
        self.assertIn('прежние данные сохранены',str(error.exception))
