import unittest
from datetime import date
import pandas as pd
from sales_center.client_segments import activity, select_block, enrich, DEFAULT_BLOCKS
from sales_center.live_data import local_id
from sales_center.snapshots import encode, decode
from fixtures import demo_data


class ClientBlocksTests(unittest.TestCase):
    def test_boundary_minimum_and_recent_order_priority(self):
        today=pd.Timestamp('2026-10-12')
        def client(cid,days,amount,recent=False):
            return dict(client_id=cid,company=str(cid),owner_employee='Менеджер',purchase_history=[dict(date=(today-pd.Timedelta(days=d)).isoformat(),amount=amount) for d in days],recent_order_dates=[today.isoformat()] if recent else [])
        frame=activity(pd.DataFrame([client(1,[0,29],100),client(2,[30],200),client(3,[60],300),client(4,[90],400),client(5,[1],500),client(6,[31],1,True)]),today)
        selected=[select_block(frame,b,today) for b in DEFAULT_BLOCKS]
        self.assertEqual(selected[0].client_id.tolist(),[1])
        self.assertEqual(selected[1].client_id.tolist(),[6,2])
        self.assertEqual(selected[2].client_id.tolist(),[3])
        self.assertEqual(selected[3].client_id.tolist(),[4])
        self.assertEqual(selected[0].total_amount.sum(),200)
        self.assertEqual(frame.set_index('client_id').loc[1,'purchase_count'],2)

    def test_enrichment_uses_owner_and_created_not_order_moment(self):
        c=pd.DataFrame([dict(client_id=local_id('c'),company='Клиент')])
        cp=[dict(id='c',owner={'id':'e'})]
        shipments=[dict(id='s',applicable=True,moment='2020-01-01',sum=12345,agent={'id':'c'})]
        new=[dict(created='2026-10-11',moment='2020-01-01',agent={'id':'c'})]
        result=enrich(c,cp,[dict(id='e',name='Анна')],shipments,new,date(2026,10,12))
        row=activity(result,date(2026,10,12)).iloc[0]
        self.assertEqual(row.owner_employee,'Анна')
        self.assertEqual(row.total_amount,123.45)
        self.assertEqual(row.recent_orders,1)

    def test_snapshot_preserves_client_history(self):
        frames=list(demo_data(date(2026,10,12)))
        frames[0].attrs['account_id']='test'
        frames[0]['purchase_history']=[[dict(date='2020-01-01',amount=123.45)] for _ in range(len(frames[0]))]
        frames[0]['crm_history_loaded']=True
        restored,_=decode(encode(frames,1234))
        self.assertEqual(restored[0].iloc[0].purchase_history[0]['amount'],123.45)
