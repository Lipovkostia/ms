from pathlib import Path
from datetime import date
import tempfile
import unittest
from unittest.mock import patch
from sales_center.storage import Store
from sales_center.sync import refresh,due
from sales_center.moysklad import MoySkladError
from sales_center.providers import GreenAPI,Telegram,MAX,OpenRouter,ProviderError
import test_integration
from sales_center.live_data import normalize

class ServicesTests(unittest.TestCase):
    def test_storage_account_and_user_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'db.sqlite'
            a=Store(path,scope='account:user-a');b=Store(path,scope='account:user-b');c=Store(path,scope='other:user-a')
            a.add(1,'Звонок',date.today());a.put('draft',1,'Текст');a.process('1:return');a.put('preference','model','model-a')
            self.assertEqual(len(b.tasks()),0);self.assertEqual(len(c.tasks()),0)
            b.update(a.tasks().iloc[0].id,'Выполнена','')
            self.assertEqual(a.tasks().iloc[0].status,'Запланирована')
            self.assertIsNone(b.get('draft',1));self.assertEqual(len(b.processed()),0)
            restored=Store(path,scope='account:user-a')
            self.assertEqual(restored.get('draft',1),'Текст')
            self.assertEqual(restored.get('preference','model'),'model-a')
            self.assertEqual(restored.processed().iloc[0].recommendation_id,'1:return')
    def test_failed_refresh_preserves_data_and_throttles_retry(self):
        state={'live_data':'old','live_analytics':'old-summary','sync_token':'test'}
        with patch('sales_center.sync.load_live',side_effect=MoySkladError('failure')):
            with self.assertRaises(MoySkladError): refresh(state,date.today())
        self.assertEqual(state['live_data'],'old');self.assertEqual(state['live_analytics'],'old-summary')
        self.assertFalse(due(state,15,now=state['sync_attempt_at']+899))
        self.assertTrue(due(state,15,now=state['sync_attempt_at']+900))
        self.assertFalse(due(state,0,now=10**12))
    def test_nullable_optional_numeric_fields(self):
        args=test_integration.IntegrationTests().fixtures();pos=args[4]['order'][0]
        pos['discount']=None;pos['vat']=None;args[2][0]['sum']=24000
        self.assertEqual(normalize(*args)[2].iloc[0].revenue,240)
        pos['quantity']=None
        with self.assertRaisesRegex(MoySkladError,'quantity'):normalize(*args)
    def test_missing_date_is_rejected(self):
        args=test_integration.IntegrationTests().fixtures();args[2][0]['moment']=None
        with self.assertRaisesRegex(MoySkladError,'moment'):normalize(*args)
    def test_provider_checks_and_model(self):
        with patch('sales_center.providers.request',return_value={'stateInstance':'notAuthorized'}):
            self.assertEqual(GreenAPI('123','test').state(),'notAuthorized')
        with patch('sales_center.providers.request',return_value={'ok':True,'result':{'username':'bot'}}):
            self.assertEqual(Telegram('123:test').state(),'bot')
        with patch('sales_center.providers.request',return_value={'user_id':1,'name':'bot'}) as call:
            self.assertEqual(MAX('test').state(),'bot');self.assertEqual(call.call_args.args[1],'https://platform-api2.max.ru/me')
        with patch('sales_center.providers.request',return_value={'choices':[{'message':{'content':'draft'}}]}) as call:
            self.assertEqual(OpenRouter('test').draft('vendor/model',{'average':100}),'draft')
            self.assertEqual(call.call_args.args[3]['model'],'vendor/model')
    def test_network_errors_do_not_leak_token_urls(self):
        import requests
        with patch('sales_center.providers.requests.request',side_effect=requests.ConnectionError('secret-url-token')):
            with self.assertRaises(ProviderError) as error:Telegram('123:test').state()
        self.assertNotIn('secret-url',str(error.exception))
