"""Dashboard real-field mapping, inclusive dates and safe partial refresh."""
from datetime import date
import unittest
from unittest.mock import patch
import pandas as pd
from sales_center.dashboard_data import metadata,attach,listing,select,merge_counterparties
from sales_center.dashboard_api import load_counterparties
from sales_center.activity_api import ClientActivityClient
from sales_center.live_data import local_id
from sales_center.moysklad import MoySkladError
from sales_center.snapshots import encode,decode
from sales_center.fast_sync import start,finish
from fixtures import demo_data


class DashboardTests(unittest.TestCase):
    def counterparties(self):
        return [dict(id='a',accountId='test',name='Альфа',created='2026-10-01 00:00:00',code='опт',owner={'id':'e'},attributes=[{'name':'Проект','value':{'id':'p','name':'Рестораны'}}]),
            dict(id='b',accountId='test',name='Бета',created='2026-10-16 23:59:59.999',code='',attributes=[{'name':'Проект','value':None}]),
            dict(id='c',accountId='test',name='Гамма',created='2026-10-17 00:00:00',code='розница',archived=True)]

    def clients(self):
        c=pd.DataFrame([{'client_id':local_id(v['id']),'company':v['name'],'segment':'Опт','city':''} for v in self.counterparties()])
        c.attrs['account_id']='test'
        return c

    def frame(self):
        return attach(self.clients(),self.counterparties(),[dict(id='e',name='Анна')],1234)

    def test_creation_date_end_inclusive_and_both_sorts(self):
        frame=listing(self.frame(),True)
        current=select(frame,date(2026,10,1),date(2026,10,16))
        self.assertEqual(current.company.tolist(),['Бета','Альфа'])
        self.assertEqual(select(frame,date(2026,10,1),date(2026,10,16),oldest_first=True).company.tolist(),['Альфа','Бета'])
        self.assertEqual(len(listing(self.frame())),2)

    def test_combined_filters_blank_code_and_literal_search(self):
        frame=listing(self.frame())
        self.assertEqual(select(frame,owners=['Анна'],projects=['Рестораны'],codes=['опт'],query='АЛЬ').company.tolist(),['Альфа'])
        self.assertEqual(select(frame,codes=['Не указан']).company.tolist(),['Бета'])
        self.assertTrue(select(frame,query='.*').empty)
        self.assertEqual(select(frame,owners=['Не назначен']).company.tolist(),['Бета'])

    def test_project_only_from_explicit_custom_field_and_missing_dates_stay_unknown(self):
        cp=[dict(id='a',updated='2026-10-01',project={'name':'Не поле контрагента'},tags=['Рестораны']),
            dict(id='b',created='2026-10-01T22:30:00Z',attributes=[{'name':' Проект ','value':'Гостиницы'}])]
        frame=metadata(cp)
        self.assertEqual(frame.crm_project.tolist(),['','Гостиницы'])
        self.assertIsNone(frame.iloc[0].created_at)
        self.assertEqual(frame.iloc[1].created_at,'2026-10-02T01:30:00')
        with self.assertRaises(MoySkladError): metadata([dict(id='bad',created='не дата')])

    def test_metadata_refresh_preserves_history_and_adds_new_client_exact_id(self):
        clients=self.clients().iloc[:1].copy()
        clients['purchase_history']=[[{'date':'2020-01-01','amount':123.45}]]
        clients['recent_order_dates']=[['2026-10-10']]
        clients['crm_history_loaded']=True
        result=merge_counterparties(clients,self.counterparties(),[],1234).set_index('client_id')
        self.assertEqual(result.loc[local_id('a'),'purchase_history'][0]['amount'],123.45)
        self.assertEqual(result.loc[local_id('a'),'recent_order_dates'],['2026-10-10'])
        self.assertFalse(result.loc[local_id('b'),'crm_history_loaded'])
        self.assertEqual(result.loc[local_id('b'),'purchase_history'],[])
        self.assertIn(local_id('c'),result.index)
        self.assertGreater(local_id('c'),2**53)

    def test_account_mismatch_rejected_before_changing_base(self):
        clients=self.clients();cp=self.counterparties();cp[0]['accountId']='other'
        with self.assertRaises(MoySkladError): merge_counterparties(clients,cp,[],1234)
        self.assertNotIn('dashboard_loaded',clients)

    def test_snapshot_preserves_metadata_and_large_ids(self):
        frames=list(demo_data(date(2026,10,16)));frames[0]=self.frame()
        restored,_=decode(encode(frames,1234))
        self.assertEqual(restored[0].client_id.tolist(),self.frame().client_id.tolist())
        self.assertEqual(listing(restored[0]).crm_project.tolist(),['Рестораны','Не указан'])

    def test_api_reads_only_counterparties_and_employees_and_closes(self):
        cp=self.counterparties();calls=[]
        def read(api,entity,params=None,progress=None):
            calls.append((entity,params))
            if entity=='employee': return [dict(id='e',name='Анна')]
            return [c for c in cp if bool(c.get('archived'))==bool(params)]
        with patch.object(ClientActivityClient,'list_entities',read),patch('requests.Session.close') as close:
            fresh=load_counterparties('test-only',self.clients())
        self.assertEqual([c[0] for c in calls],['counterparty','counterparty','employee'])
        self.assertEqual(listing(fresh).owner_employee.iloc[0],'Анна')
        close.assert_called_once()

    def test_invalid_response_leaves_old_snapshot_untouched(self):
        clients=self.clients()
        with patch.object(ClientActivityClient,'list_entities',return_value=['invalid']),patch('requests.Session.close') as close:
            with self.assertRaises(MoySkladError): load_counterparties('test-only',clients)
        self.assertNotIn('dashboard_loaded',clients)
        close.assert_called_once()

    def test_background_refresh_keeps_sales_and_timestamp(self):
        frames=list(demo_data(date(2026,10,16)));frames[0]=self.clients();frames=tuple(frames)
        fresh=self.frame();state=dict(live_data=frames,sync_success_at=100,sync_attempt_at=90)
        with patch('sales_center.dashboard_api.load_counterparties',return_value=fresh) as crm,patch('sales_center.sync.load_live') as full:
            self.assertTrue(start(state,date(2026,10,16),'test-only','u',kind='counterparties'))
            state['live_refresh_job'].future.result(timeout=10)
            self.assertTrue(finish(state,'u'))
        crm.assert_called_once();full.assert_not_called()
        self.assertEqual(state['sync_success_at'],100)
        self.assertEqual(state['sync_attempt_at'],90)
        self.assertIs(state['live_data'][1],frames[1])
        self.assertIs(state['live_data'][2],frames[2])
