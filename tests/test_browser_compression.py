"""Device snapshots stay bounded, authenticated and compatible after upgrades."""
import base64
from datetime import date
import hashlib
import hmac
import json
import unittest
from unittest.mock import patch
import zlib
import pandas as pd
from fixtures import demo_data
from sales_center.device_storage import seal_snapshot, unseal_snapshot
from sales_center.snapshots import encode, source_id, SnapshotError


class BrowserCompressionTests(unittest.TestCase):
    def setUp(self):
        self.token='synthetic-device-compression-key'
        self.frames=demo_data(date(2026,10,12))
        self.frames[0].attrs['account_id']='synthetic-compression-account'

    def signed_compressed(self,packed):
        envelope={'version':2,'encoding':'zlib-base64','source':source_id(self.token),
                  'payload':base64.b64encode(packed).decode('ascii')}
        raw=json.dumps(envelope,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
        envelope['signature']=hmac.new(self.token.encode(),('device-snapshot-v2:'+raw).encode(),hashlib.sha256).hexdigest()
        return json.dumps(envelope)

    def large_snapshot(self):
        clients,products,lines=self.frames
        clients=clients.copy()
        clients['phone']='synthetic-'*2500
        clients.loc[0,'client_id']=2**59+123
        return clients,products,lines

    def test_large_snapshots_compress_without_rounding_or_losing_data(self):
        frames=self.large_snapshot()
        text=seal_snapshot(frames,1000,self.token)
        raw=json.dumps(encode(frames,1000),ensure_ascii=False)
        self.assertEqual(json.loads(text)['encoding'],'zlib-base64')
        self.assertLess(len(text.encode()),len(raw.encode())*.4)
        self.assertNotIn(self.token,text)
        restored,saved_at=unseal_snapshot(text,self.token)
        self.assertEqual(saved_at,1000)
        self.assertEqual(int(restored[0].iloc[0].client_id),2**59+123)
        for actual,expected in zip(restored,frames):
            pd.testing.assert_frame_equal(actual,expected,check_dtype=False)

    def test_previous_uncompressed_records_still_restore(self):
        raw=json.dumps(encode(self.frames,1234),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
        envelope={'source':source_id(self.token),'payload':raw,
                  'signature':hmac.new(self.token.encode(),('device-snapshot-v1:'+raw).encode(),hashlib.sha256).hexdigest()}
        restored,saved_at=unseal_snapshot(json.dumps(envelope),self.token)
        self.assertEqual(saved_at,1234)
        self.assertEqual(len(restored[2]),len(self.frames[2]))

    def test_compressed_metadata_payload_and_key_are_authenticated(self):
        text=seal_snapshot(self.large_snapshot(),1000,self.token)
        with self.assertRaises(SnapshotError):unseal_snapshot(text,'another-device-key')
        for field,value in [('version',3),('encoding','identity'),('source','another-source'),('payload','eA=='),('extra','unsigned')]:
            envelope=json.loads(text);envelope[field]=value
            with self.subTest(field=field), self.assertRaises(SnapshotError):
                unseal_snapshot(json.dumps(envelope),self.token)

    def test_authenticated_oversized_decompression_is_bounded(self):
        text=self.signed_compressed(zlib.compress(b' '*4096))
        with patch('sales_center.device_storage.MAX_SNAPSHOT_BYTES',1024):
            with self.assertRaises(SnapshotError):unseal_snapshot(text,self.token)
            with self.assertRaises(SnapshotError):seal_snapshot(self.frames,1000,self.token)

    def test_truncated_and_trailing_compressed_streams_are_rejected(self):
        packed=zlib.compress(json.dumps(encode(self.frames,1000)).encode())
        for invalid in [packed[:-1],packed+b'trailing',packed+packed]:
            with self.subTest(length=len(invalid)), self.assertRaises(SnapshotError):
                unseal_snapshot(self.signed_compressed(invalid),self.token)


    def test_legacy_browser_transport_preserves_signature_and_ids(self):
        import base64,zlib
        frames=self.frames
        packed=seal_snapshot(frames,1000,'test-only')
        transport=json.dumps({'transport':'zlib-base64','data':base64.b64encode(zlib.compress(packed.encode())).decode()})
        restored,saved_at=unseal_snapshot(transport,'test-only')
        self.assertEqual(saved_at,1000)
        self.assertEqual(restored[0].iloc[0].client_id,frames[0].iloc[0].client_id)
        with self.assertRaises(SnapshotError): unseal_snapshot(transport,'other-key')

if __name__=='__main__':unittest.main()
