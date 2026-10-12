from datetime import date
import unittest
from unittest.mock import Mock,patch
from sales_center.device_storage import render_and_restore,seal_snapshot
from fixtures import demo_data


class BrowserIdleTests(unittest.TestCase):
    def test_restore_then_small_ack_does_not_create_nonce_loop(self):
        frames=demo_data(date(2026,10,12));frames[0].attrs['account_id']='test'
        state={'_device_command':{'operation':'load','request_id':'first'}}
        component=Mock(return_value={'owner':'u','request_id':'first','status':'restored','token':'test-only','snapshot_json':seal_snapshot(frames,1000,'test-only')})
        with patch('sales_center.device_storage.components.declare_component',return_value=component):
            render_and_restore(state,'u',date(2026,10,12))
            self.assertIn('live_data',state)
            idle=state['_device_command']
            self.assertEqual(idle['operation'],'idle')
            self.assertNotIn('snapshot_json',idle)
            self.assertNotIn('token',idle)
            component.return_value={'owner':'u','request_id':idle['request_id'],'status':'idle'}
            for _ in range(3): render_and_restore(state,'u',date(2026,10,12))
            self.assertIs(state['_device_command'],idle)
            self.assertEqual(component.call_count,4)
