from datetime import date
import unittest
from unittest.mock import patch
import pandas as pd
from sales_center.dashboard_data import attach
from sales_center.dashboard_workspace import attach_orders,client_facts,with_tasks,subset,sort_clients
from sales_center.dashboard_api import load_counterparties
from sales_center.activity_api import ClientActivityClient
from sales_center.live_data import local_id
from sales_center.moysklad import MoySkladError


class ManagerDashboardTests(unittest.TestCase):
    day=date(2026,10,17)

    def clients(self):
        cp=[dict(id=str(i),accountId='test',name=f'Клиент {i}',created='2026-10-16',owner={'id':'e'} if i!=6 else {}) for i in range(8)]
        clients=pd.DataFrame([dict(client_id=local_id(c['id']),company=c['name'],segment='',city='') for c in cp])
        clients.attrs['account_id']='test'
        clients=attach(clients,cp,[dict(id='e',name='Анна')],1234)
        clients['purchase_history']=[[] for _ in cp];clients['crm_history_loaded']=True
        for i,days in [(2,[80,70,60]),(3,[100,70,40]),(7,[40])]:
            clients.at[i,'purchase_history']=[dict(date=(pd.Timestamp(self.day)-pd.Timedelta(days=d)).isoformat(),amount=100) for d in days]
        docs=[dict(id='old',agent={'id':'1'},created='2020-01-01'),dict(id='new',agent={'id':'7'},created='2026-10-16')]
        clients=attach_orders(clients,docs,self.day)
        clients.loc[4,['crm_orders_loaded','crm_history_loaded']]=False
        return clients

    def test_order_and_purchase_counts_are_distinct_and_unknown_is_not_zero(self):
        base=client_facts(self.clients(),self.day)
        result=with_tasks(base,pd.DataFrame(),self.day).set_index('company')
        self.assertEqual(result.loc['Клиент 1','orders'],1)
        self.assertEqual(result.loc['Клиент 1','purchases'],0)
        self.assertEqual(result.loc['Клиент 1','attention_status'],'Первый заказ')
        self.assertEqual(result.loc['Клиент 0','attention_status'],'Первый контакт')
        self.assertTrue(pd.isna(result.loc['Клиент 4','orders']))
        self.assertTrue(pd.isna(result.loc['Клиент 4','purchases']))
        self.assertEqual(result.loc['Клиент 4','attention_status'],'Уточнить данные')
        self.assertFalse(result.loc['Клиент 4','attention'])
        self.assertEqual(result.loc['Клиент 2','turnover'],300)

    def test_attention_uses_individual_cycles_and_recent_order_takes_precedence(self):
        result=with_tasks(client_facts(self.clients(),self.day),pd.DataFrame(),self.day).set_index('company')
        self.assertEqual(result.loc['Клиент 2','attention_status'],'Пора повторить заказ')
        self.assertEqual(result.loc['Клиент 3','attention_status'],'Есть покупки')
        self.assertEqual(result.loc['Клиент 7','attention_status'],'Новый заказ')
        self.assertEqual(result.loc['Клиент 6','attention_status'],'Нет менеджера')

    def test_tasks_due_future_done_and_sort_priority(self):
        tasks=pd.DataFrame([dict(id=1,client_id=local_id('0'),status='В работе',due='2026-10-18'),
            dict(id=2,client_id=local_id('5'),status='Запланирована',due='2026-10-16'),
            dict(id=3,client_id=local_id('1'),status='Выполнена',due='2026-10-10')])
        result=with_tasks(client_facts(self.clients(),self.day),tasks,self.day)
        by_name=result.set_index('company')
        self.assertEqual(by_name.loc['Клиент 0','attention_status'],'В работе')
        self.assertFalse(by_name.loc['Клиент 0','attention'])
        self.assertEqual(subset(result,'due').company.tolist(),['Клиент 5'])
        self.assertEqual(sort_clients(result,'Сначала важные').company.iloc[0],'Клиент 5')
        self.assertEqual(by_name.loc['Клиент 1','attention_status'],'Первый заказ')

    def test_cached_snapshot_ages_recent_order_and_new_client(self):
        frame=self.clients()
        later=client_facts(frame,date(2026,11,20))
        self.assertFalse(later.recent_order.any())
        self.assertFalse(later.is_new.any())

    def test_duplicate_or_foreign_order_cannot_publish_a_partial_summary(self):
        clients=self.clients();doc=dict(id='a',agent={'id':'0'},created='2026-10-15')
        for documents in [[doc,doc],[dict(doc,accountId='other')]]:
            with self.assertRaises(MoySkladError): attach_orders(clients,documents,self.day)
        self.assertEqual(clients.crm_order_count.sum(),2)

    def test_crm_refresh_reads_headers_only_and_populates_history_for_new_clients(self):
        clients=self.clients().iloc[:2].copy();cp=[dict(id='0',accountId='test',name='Клиент 0'),dict(id='new-client',accountId='test',name='Новый')]
        source={'counterparty':cp,'employee':[],'currency':[dict(id='rub',isoCode='RUB')],
            'demand':[dict(id='s',applicable=True,agent={'id':'new-client'},moment='2026-10-10',sum=50000,rate={'currency':{'id':'rub'}})],
            'customerorder':[dict(id='o',agent={'id':'new-client'},created='2026-10-09')]}
        calls=[]
        def read(api,entity,params=None,progress=None):
            calls.append((entity,params));return [] if params=={'filter':'archived=true'} else source[entity]
        with patch.object(ClientActivityClient,'list_entities',read),patch.object(ClientActivityClient,'demand_positions',side_effect=AssertionError('No positions')):
            result=load_counterparties('test-only',clients,include_activity=True,today=self.day)
        row=client_facts(result,self.day).set_index('company').loc['Новый']
        self.assertEqual(row.orders,1);self.assertEqual(row.purchases,1);self.assertEqual(row.turnover,500)
        historical=result.set_index('company').loc['Клиент 1']
        self.assertEqual(historical.owner_employee,'Анна')
        self.assertFalse(historical.dashboard_loaded)
        self.assertNotIn('Клиент 1',client_facts(result,self.day).company.tolist())
        self.assertEqual([c[0] for c in calls],['counterparty','counterparty','employee','currency','demand','customerorder'])
        self.assertTrue(all(not p or 'expand' not in p for _,p in calls))
