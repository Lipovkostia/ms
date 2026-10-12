from datetime import date
import unittest
import pandas as pd
from sales_center.product_analytics import buyers,price_list,category_paths
from sales_center.live_data import normalize_catalog
from sales_center.browser_store import seal_snapshot,unseal_snapshot
from sales_center.snapshots import SnapshotError
from fixtures import demo_data

class ProductBuyerTests(unittest.TestCase):
    def test_product_ids_do_not_mix_duplicate_names_and_orders(self):
        clients=pd.DataFrame({'client_id':[1,2],'company':['Клиент А','Клиент Б']})
        lines=pd.DataFrame([
            ('a',1,101,'2026-10-01',2.5,100),('a',1,101,'2026-10-01',1.5,60),
            ('b',1,101,'2026-10-10',3,120),('c',2,102,'2026-10-11',99,9000),
            ('d',2,101,'2026-10-11',0,0)],columns=['order_id','client_id','product_id','date','quantity','revenue'])
        lines['date']=pd.to_datetime(lines.date)
        result=buyers(lines,clients,101,date(2026,10,12))
        self.assertEqual(len(result),1)
        self.assertEqual(result.iloc[0].quantity,7)
        self.assertEqual(result.iloc[0].revenue,280)
        self.assertEqual(result.iloc[0].orders,2)
        self.assertEqual(result.iloc[0].days_since,2)
    def test_catalog_uses_actual_prices_groups_and_archive_flags(self):
        rows=[{'id':'one','name':'Сыр','pathName':'Испания/Сыры','salePrices':[{'value':12345,'priceType':{'id':'wholesale','name':'Опт'},'currency':{'id':'rub'}}]},
              {'id':'two','name':'Архивный','archived':True,'salePrices':[{'value':10000,'priceType':{'id':'wholesale','name':'Опт'},'currency':{'id':'rub'}}]},
              {'id':'zero','name':'Без цены','salePrices':[{'value':0,'priceType':{'id':'wholesale','name':'Опт'},'currency':{'id':'rub'}}]}]
        catalog=normalize_catalog(rows,[{'id':'rub','isoCode':'643'}])
        view=price_list(catalog,'wholesale')
        self.assertEqual(len(view),1)
        self.assertEqual(view.iloc[0].list_price,123.45)
        self.assertEqual(view.iloc[0].currency,'RUB')
        self.assertEqual(category_paths(view),['Испания','Испания/Сыры'])
        self.assertEqual(len(price_list(catalog,'wholesale',False)),2)
    def test_device_snapshot_is_signed_and_preserves_large_ids(self):
        frames=demo_data(date(2026,10,12));frames[0].attrs['account_id']='test'
        frames[0].loc[0,'client_id']=2**59+123
        text=seal_snapshot(frames,1000,'fake-device-key')
        restored,saved=unseal_snapshot(text,'fake-device-key')
        self.assertEqual(saved,1000)
        self.assertEqual(restored[0].iloc[0].client_id,2**59+123)
        self.assertNotIn('fake-device-key',text)
        with self.assertRaises(SnapshotError):unseal_snapshot(text,'different-key')
        with self.assertRaises(SnapshotError):unseal_snapshot(text.replace('1000.0','1001.0'),'fake-device-key')
