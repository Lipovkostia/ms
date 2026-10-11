from pathlib import Path
from datetime import date
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
from sales_center.connection_config import read_config
from sales_center.snapshots import SnapshotCache,SnapshotError
from sales_center.sync import refresh,restore,due
from sales_center.storage import StoreError
from sales_center.moysklad import MoySkladError
from fixtures import demo_data

class PersistentConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'data.db'
        self.fresh=demo_data(date.today())
        self.fresh[0].attrs['account_id']='test-account'
        self.fresh[2].attrs['excluded_internal_shipments']=2
    def tearDown(self): self.temp.cleanup()
    def cache(self,token='test-persistent-key',user='user-a'):
        return SnapshotCache(self.path,token,user)
    def test_secret_precedence_private_gate_and_hidden_repr(self):
        config=read_config({'MOYSKLAD_TOKEN':'test-secret','MOYSKLAD_PRIVATE_DEPLOYMENT':True},'personal',{'MOYSKLAD_TOKEN':'old-environment'})
        self.assertTrue(config.automatic);self.assertEqual(config.token,'test-secret');self.assertNotIn('test-secret',repr(config))
        self.assertFalse(read_config({'MOYSKLAD_TOKEN':'test-secret'},'personal',{}).automatic)
        self.assertTrue(read_config({'MOYSKLAD_TOKEN':'test-secret'},'oidc-user',{}).automatic)
        self.assertFalse(read_config({'MOYSKLAD_TOKEN':'test-secret','MOYSKLAD_PRIVATE_DEPLOYMENT':'false'},'personal',{}).automatic)
    def test_restart_restores_without_api_and_keeps_timestamp(self):
        cache=self.cache();state={}
        with patch('sales_center.sync.load_live',return_value=self.fresh) as api:
            refresh(state,date.today(),token='test-persistent-key',retain=True,cache=cache)
            self.assertEqual(api.call_count,1)
        previous=state['sync_success_at']
        restarted={'sync_token':'test-persistent-key'}
        with patch('sales_center.sync.load_live',side_effect=AssertionError('Restore must not read API')):
            self.assertTrue(restore(restarted,date.today(),self.cache()))
        self.assertEqual(restarted['sync_success_at'],previous)
        self.assertTrue(restarted['sync_restored'])
        pd.testing.assert_frame_equal(restarted['live_data'][2],self.fresh[2],check_dtype=False)
        self.assertEqual(restarted['live_data'][0].attrs['account_id'],'test-account')
        self.assertNotIn('test-persistent-key',cache.store.export())
    def test_cache_isolated_by_user_and_token(self):
        self.cache().save(self.fresh,1000)
        self.assertIsNone(self.cache(user='user-b').load())
        self.assertIsNone(self.cache(token='other-token').load())
    def test_large_integer_ids_missing_cost_and_empty_data_roundtrip(self):
        c,p,l=self.fresh
        big=2**59+137
        c.loc[c.index[0],'client_id']=big
        l.loc[l.index[0],'client_id']=big
        l.loc[l.index[0],'cost']=float('nan')
        self.cache().save((c,p,l),1000)
        frames,_=self.cache().load()
        self.assertEqual(int(frames[0].iloc[0].client_id),big)
        self.assertEqual(int(frames[2].iloc[0].client_id),big)
        self.assertTrue(pd.isna(frames[2].iloc[0]['cost']))
        self.cache().save((c,p,l.iloc[:0]),1000)
        frames,_=self.cache().load()
        self.assertTrue(frames[2].empty)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(frames[2].date))
    def test_failed_refresh_keeps_previous_disk_snapshot(self):
        self.cache().save(self.fresh,1000)
        state={}
        with patch('sales_center.sync.load_live',side_effect=MoySkladError('API failure')):
            with self.assertRaises(MoySkladError):refresh(state,date.today(),token='test',cache=self.cache())
        self.assertEqual(self.cache().load()[1],1000)
    def test_failed_disk_write_keeps_valid_live_data(self):
        cache=self.cache()
        with patch('sales_center.sync.load_live',return_value=self.fresh),patch.object(cache,'save',side_effect=StoreError('failure')):
            state={};refresh(state,date.today(),token='test',cache=cache)
        self.assertIn('live_data',state);self.assertIn('sync_cache_error',state)
    def test_corrupt_snapshot_is_not_silently_returned(self):
        cache=self.cache();cache.store.put('snapshot','latest',{'version':99})
        with self.assertRaises(SnapshotError):cache.load()
    def test_stale_restore_defers_network_until_next_minute(self):
        self.cache().save(self.fresh,1000)
        with patch('sales_center.sync.time.time',return_value=5000):
            state={'sync_token':'test'};restore(state,date.today(),self.cache())
        self.assertFalse(due(state,30,now=5059))
        self.assertTrue(due(state,30,now=5060))
    def test_snapshot_recovers_in_a_fresh_python_process(self):
        import subprocess
        import sys
        import os
        self.cache().save(self.fresh,1000)
        script='''
import sys
from sales_center.snapshots import SnapshotCache
from sales_center.sync import restore
from unittest.mock import patch
from datetime import date
cache=SnapshotCache(sys.argv[1],'test-persistent-key','user-a')
with patch('sales_center.sync.load_live',side_effect=AssertionError('No network on restore')):
    state={};assert restore(state,date.today(),cache)
assert len(state['live_data'][0])==100
assert state['sync_success_at']==1000
print('Restored in a new process')
'''
        env=os.environ.copy();env.pop('DATABASE_URL',None)
        result=subprocess.run([sys.executable,'-c',script,str(self.path)],cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Restored in a new process',result.stdout)
