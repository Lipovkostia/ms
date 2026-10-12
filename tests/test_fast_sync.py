from datetime import date
from threading import Event
import unittest
from unittest.mock import Mock, patch
from sales_center.fast_sync import start, finish, pending
from sales_center.moysklad import MoySkladError
from fixtures import demo_data


class BackgroundSyncTests(unittest.TestCase):
    def frames(self):
        frames=demo_data(date(2026,10,12))
        frames[0].attrs['account_id']='test'
        return frames

    def test_slow_api_keeps_snapshot_available_and_starts_only_once(self):
        previous=self.frames();fresh=self.frames()
        release=Event();entered=Event()
        def slow(*args,**kwargs):
            entered.set();release.wait(5)
            return fresh
        state={'live_data':previous,'sync_success_at':100,'sync_token':'test'}
        with patch('sales_center.sync.load_live',side_effect=slow) as api:
            try:
                self.assertTrue(start(state,date(2026,10,12),'test','u'))
                self.assertTrue(entered.wait(2))
                self.assertTrue(pending(state))
                self.assertIs(state['live_data'],previous)
                self.assertFalse(start(state,date(2026,10,12),'test','u'))
                self.assertFalse(finish(state,'u'))
                api.assert_called_once()
            finally: release.set();state['live_refresh_job'].future.result(timeout=10)
            self.assertTrue(finish(state,'u'))
        self.assertIs(state['live_data'],fresh)
        self.assertFalse(pending(state))

    def test_failure_preserves_old_data_and_saved_timestamp(self):
        frames=self.frames();state={'live_data':frames,'sync_success_at':100,'sync_token':'old'}
        with patch('sales_center.sync.load_live',side_effect=MoySkladError('Нет связи')):
            start(state,date(2026,10,12),'test','u')
            try: state['live_refresh_job'].future.result(timeout=10)
            except MoySkladError: pass
            self.assertFalse(finish(state,'u'))
        self.assertIs(state['live_data'],frames)
        self.assertEqual(state['sync_success_at'],100)
        self.assertEqual(state['sync_token'],'old')
        self.assertIn('Нет связи',state['live_error'])

    def test_owner_and_source_change_discard_results(self):
        for changed in ['owner','source']:
            state={}
            with patch('sales_center.sync.load_live',return_value=self.frames()):
                start(state,date(2026,10,12),'test','u')
                state['live_refresh_job'].future.result(timeout=10)
                if changed=='source': state['sync_pending_token']='other'
                self.assertFalse(finish(state,'other' if changed=='owner' else 'u'))
            self.assertNotIn('live_data',state)

    def test_catalog_refresh_reads_no_shipments_and_preserves_history_timestamp(self):
        frames=self.frames();new_products=frames[1].copy()
        state={'live_data':frames,'sync_success_at':100,'sync_attempt_at':90,'sync_origin':'device'}
        with patch('sales_center.price_catalog.load_catalog',return_value=new_products) as catalogue,patch('sales_center.sync.load_live') as shipments:
            start(state,date(2026,10,12),'test','u',kind='catalog')
            state['live_refresh_job'].future.result(timeout=10)
            self.assertTrue(finish(state,'u'))
            catalogue.assert_called_once();shipments.assert_not_called()
        self.assertEqual(state['sync_success_at'],100)
        self.assertEqual(state['sync_attempt_at'],90)
        self.assertIs(state['live_data'][1],new_products)
        self.assertIs(state['live_data'][2],frames[2])

    def test_bad_cache_does_not_drop_successful_refresh(self):
        from sales_center.storage import StoreError
        state={};cache=Mock();cache.save.side_effect=StoreError('storage')
        with patch('sales_center.sync.load_live',return_value=self.frames()):
            start(state,date(2026,10,12),'test','u',cache=cache)
            state['live_refresh_job'].future.result(timeout=10)
            self.assertTrue(finish(state,'u'))
        self.assertIn('live_data',state)
        self.assertIn('sync_cache_error',state)
