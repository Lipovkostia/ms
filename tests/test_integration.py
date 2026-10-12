import unittest
from unittest.mock import Mock, patch
import pandas as pd
from sales_center.moysklad import MoySkladClient, MoySkladError
from sales_center.live_data import normalize
from sales_center.analytics import metrics, orders

class IntegrationTests(unittest.TestCase):
    def fixtures(self):
        cp=[{'id':'client','name':'Тестовая компания'}]
        products=[{'id':'cheese','name':'Сыр','pathName':'Сыры'}]
        cur=[{'id':'rub','isoCode':'643'}]
        doc={'id':'order','agent':{'id':'client'},'rate':{'currency':{'id':'rub'}},
             'moment':'2026-10-10 12:00:00','applicable':True,'vatEnabled':True,'vatIncluded':True,'sum':21600}
        pos={'quantity':2,'price':12000,'discount':10,'vat':20,'assortment':products[0], 'stock':{'cost':5000}}
        return cp,products,[doc],cur,{'order':[pos]}
    def test_vat_discount_cost(self):
        _,_,lines=normalize(*self.fixtures())
        self.assertEqual(lines.iloc[0].revenue,180)
        self.assertEqual(lines.iloc[0]['cost'],100)
        self.assertEqual(lines.iloc[0].profit,80)
    def test_missing_cost_never_zero(self):
        args=self.fixtures()
        del args[4]['order'][0]['stock']
        _,_,lines=normalize(*args)
        self.assertTrue(pd.isna(metrics(lines)['profit']))
        self.assertTrue(pd.isna(orders(lines).iloc[0].profit))
    def test_reject_inconsistent_or_foreign_data(self):
        args=self.fixtures()
        args[2][0]['sum']=999
        with self.assertRaises(MoySkladError): normalize(*args)
        args=self.fixtures()
        args[3][0]['isoCode']='978'
        with self.assertRaises(MoySkladError): normalize(*args)
    def test_no_credentials(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(MoySkladError): MoySkladClient()
    def test_pagination(self):
        with patch.dict('os.environ',{'MOYSKLAD_TOKEN':'test-only'}):
            client=MoySkladClient()
        client._get=Mock(side_effect=[{'rows':[{'id':i} for i in range(1000)],'meta':{'size':1001}}, {'rows':[{'id':1000}],'meta':{'size':1001}}])
        self.assertEqual(len(client.list_entities('counterparty')),1001)
        self.assertEqual(client._get.call_args_list[1].args[1]['offset'],1000)
        with self.assertRaises(ValueError): client.list_entities('untrusted')
    def test_access_denied(self):
        with patch.dict('os.environ',{'MOYSKLAD_TOKEN':'test-only'}):
            client=MoySkladClient()
        client.session.get=Mock(return_value=Mock(status_code=403))
        with self.assertRaisesRegex(MoySkladError,'отклонил доступ'):
            client.list_entities('counterparty')

    def test_rub_letter_code(self):
        args=self.fixtures()
        args[3][0]['isoCode']='RUB'
        self.assertEqual(len(normalize(*args)[2]),1)

    def test_expanded_positions_avoid_per_shipment_requests(self):
        from sales_center.live_data import load_live
        from datetime import date
        cp,products,docs,cur,positions=self.fixtures()
        docs[0]['positions']={'rows':positions['order'],'meta':{'size':1}}
        with patch('sales_center.live_data.MoySkladClient') as factory:
            api=factory.return_value
            api.list_entities.side_effect=[cur,docs,cp,products,[],docs,[]]
            progress=Mock()
            result=load_live(date(2026,10,12),token='test-only',progress=progress)
            self.assertEqual(len(result[2]),1)
            api.demand_positions.assert_not_called()
            self.assertEqual(api.list_entities.call_args_list[1].args[1]['expand'],'positions.assortment')
            self.assertTrue(progress.called)
            api.session.close.assert_called_once()

    def test_parallel_shipments_keep_every_page_in_order(self):
        with patch.dict('os.environ',{'MOYSKLAD_TOKEN':'test-only'}):
            client=MoySkladClient()
        client._get=Mock(return_value={'rows':[{'id':i} for i in range(100)],'meta':{'size':201}})
        def page(path,params):
            off=params['offset']
            return {'rows':[{'id':i} for i in range(off,min(off+100,201))]}
        client._parallel_page=Mock(side_effect=page)
        progress=Mock()
        rows=client.list_entities('demand',{'fields':'stock'},progress=progress)
        self.assertEqual([r['id'] for r in rows],list(range(201)))
        self.assertEqual(client._parallel_page.call_count,2)
        self.assertEqual(progress.call_args.args,(201,201))

    def test_internal_organization_shipments_are_explicitly_excluded(self):
        args=self.fixtures()
        args[2][0]['agent']={'meta':{'type':'organization','href':'https://api.moysklad.ru/api/remap/1.2/entity/organization/own'}}
        clients,products,lines=normalize(*args)
        self.assertTrue(lines.empty)
        self.assertEqual(lines.attrs['excluded_internal_shipments'],1)

    def test_transient_read_timeout_retries_without_losing_request(self):
        import requests
        with patch.dict('os.environ',{'MOYSKLAD_TOKEN':'test-only'}):
            client=MoySkladClient()
        response=Mock(status_code=200)
        response.json.return_value={'rows':[],'meta':{'size':0}}
        client.session.get=Mock(side_effect=[requests.ReadTimeout(),response])
        with patch('sales_center.moysklad.time.sleep'):
            self.assertEqual(client.list_entities('currency'),[])
        self.assertEqual(client.session.get.call_count,2)
        self.assertEqual(client.session.get.call_args.kwargs['timeout'],(10,90))

    def test_empty_zero_value_shipments_are_not_purchases(self):
        args=self.fixtures()
        args[2][0]['sum']=0
        args[4]['order']=[]
        lines=normalize(*args)[2]
        self.assertTrue(lines.empty)
        self.assertEqual(lines.attrs['excluded_empty_shipments'],1)
