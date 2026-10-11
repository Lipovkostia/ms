import tempfile
import unittest
from datetime import date
from pathlib import Path
import pandas as pd
from fixtures import demo_data
from sales_center.analytics import metrics, orders, client_summary, companions, period
from sales_center.recommendations import generate
from sales_center.storage import Store

class AnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.today = date(2026,10,11)
        cls.clients,cls.products,cls.lines = demo_data(cls.today)
    def test_data_and_accounting(self):
        self.assertEqual(len(self.clients),100)
        self.assertTrue((self.lines.date <= pd.Timestamp(self.today)).all())
        self.assertTrue((self.lines.date >= pd.Timestamp(self.today)-pd.DateOffset(months=12)).all())
        self.assertAlmostEqual(self.lines.profit.sum(),self.lines.revenue.sum()-self.lines.cost.sum())
        m = metrics(self.lines)
        self.assertEqual(m['orders'],self.lines.order_id.nunique())
        self.assertAlmostEqual(m['average'],self.lines.revenue.sum()/m['orders'])
        self.assertAlmostEqual(m['margin'],self.lines.profit.sum()/self.lines.revenue.sum()*100)
        self.assertGreater(len(self.lines),1000)
    def test_individual_cycle(self):
        client = self.clients.iloc[:2].copy()
        own = self.lines.iloc[:1].copy()
        frames = []
        for cid,gap in [(1,10),(2,60)]:
            for index,back in enumerate([gap*2+20,gap+20,20]):
                line = own.copy()
                line['client_id']=cid
                line['order_id']=cid*100+index
                line['date']=pd.Timestamp(self.today)-pd.Timedelta(days=back)
                frames.append(line)
        s = client_summary(client,pd.concat(frames),self.today).set_index('client_id')
        self.assertEqual(s.loc[1,'cycle'],10)
        self.assertEqual(s.loc[2,'cycle'],60)
        self.assertEqual(s.loc[1,'priority'],'Высокий')
        self.assertEqual(s.loc[2,'priority'],'Низкий')
    def test_empty_period(self):
        empty = period(self.lines,date(2000,1,1),date(2000,1,2))
        self.assertEqual(metrics(empty)['orders'],0)
        self.assertEqual(metrics(empty)['margin'],0)
        s = client_summary(self.clients,empty,self.today)
        self.assertTrue(s.cycle.isna().all())
        self.assertTrue(generate(s,empty,self.products,self.today).empty)
    def test_pairs_count_orders_not_lines(self):
        data = pd.DataFrame({'order_id':[1,1,1,2,2],'product':['A','A','B','A','B']})
        self.assertEqual(companions(data).iloc[0]['Совместных заказов'],2)
    def test_recommendations(self):
        s = client_summary(self.clients,self.lines,self.today)
        r = generate(s,self.lines,self.products,self.today)
        self.assertFalse(r.empty)
        self.assertTrue(r.id.is_unique)
        self.assertTrue((r.effect >= 0).all())
        for cid in r[r.kind == 'return'].client_id:
            self.assertGreater(s.set_index('client_id').loc[cid,'cycle_ratio'],1.5)
    def test_sqlite_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'tasks.db'
            store = Store(path)
            store.add(1,'Позвонить',self.today,'Черновик','1:return')
            fresh = Store(path)
            self.assertEqual(len(fresh.tasks()),1)
            fresh.update(1,'Выполнена','Потребность уточнена')
            self.assertEqual(store.tasks().iloc[0]['status'],'Выполнена')
            store.process('1:return'); store.process('1:return')
            self.assertEqual(len(store.processed()),1)
            with self.assertRaises(ValueError): store.add(1,' ',self.today)

if __name__ == '__main__':
    unittest.main()
