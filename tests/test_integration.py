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
        client._get=Mock(side_effect=[{'rows':[{'id':i} for i in range(100)],'meta':{'size':101}}, {'rows':[{'id':100}],'meta':{'size':101}}])
        self.assertEqual(len(client.list_entities('counterparty')),101)
        self.assertEqual(client._get.call_args_list[1].args[1]['offset'],100)
        with self.assertRaises(ValueError): client.list_entities('untrusted')
    def test_access_denied(self):
        with patch.dict('os.environ',{'MOYSKLAD_TOKEN':'test-only'}):
            client=MoySkladClient()
        client.session.get=Mock(return_value=Mock(status_code=403))
        with self.assertRaisesRegex(MoySkladError,'отклонил доступ'):
            client.list_entities('counterparty')
