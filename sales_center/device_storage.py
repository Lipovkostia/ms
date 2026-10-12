"""Browser-local encrypted persistence; secrets never enter server records or Git."""
from pathlib import Path
import base64
import hashlib
import hmac
import json
import time
import uuid
import zlib
import streamlit.components.v1 as components
from .snapshots import encode,decode,SnapshotError,source_id
from .sync import assign

MAX_SNAPSHOT_BYTES=64*1024*1024
COMPRESSION_THRESHOLD=1024*1024


def _signed_envelope(envelope,token):
    raw=json.dumps(envelope,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    return hmac.new(token.encode(),('device-snapshot-v2:'+raw).encode(),hashlib.sha256).hexdigest()


def seal_snapshot(frames,saved_at,token):
    raw=json.dumps(encode(frames,saved_at),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    raw_bytes=raw.encode()
    if len(raw_bytes)>MAX_SNAPSHOT_BYTES:
        raise SnapshotError('Снимок слишком большой для сохранения на устройстве. Текущие данные доступны в этой сессии.')
    if len(raw_bytes)>=COMPRESSION_THRESHOLD:
        envelope={'version':2,'encoding':'zlib-base64','source':source_id(token),
            'payload':base64.b64encode(zlib.compress(raw_bytes)).decode('ascii')}
        envelope['signature']=_signed_envelope(envelope,token)
        return json.dumps(envelope,ensure_ascii=False,separators=(',',':'))
    signature=hmac.new(token.encode(),('device-snapshot-v1:'+raw).encode(),hashlib.sha256).hexdigest()
    return json.dumps({'source':source_id(token),'payload':raw,'signature':signature},ensure_ascii=False)


def unseal_snapshot(text,token):
    try:
        if not isinstance(text,str) or len(text.encode())>MAX_SNAPSHOT_BYTES*2+1024: raise ValueError()
        envelope=json.loads(text)
        if isinstance(envelope,dict) and envelope.get('transport')=='zlib-base64':
            packed=base64.b64decode(envelope['data'],validate=True)
            stream=zlib.decompressobj()
            unpacked=stream.decompress(packed,MAX_SNAPSHOT_BYTES*2+1025)
            if len(unpacked)>MAX_SNAPSHOT_BYTES*2+1024 or stream.unconsumed_tail or not stream.eof or stream.unused_data: raise ValueError()
            envelope=json.loads(unpacked.decode('utf-8'))

        if not isinstance(envelope,dict) or not isinstance(envelope.get('payload'),str): raise ValueError()
        if envelope.get('version',1)==1:
            raw=envelope['payload']
            if len(raw.encode())>MAX_SNAPSHOT_BYTES: raise ValueError()
            expected=hmac.new(token.encode(),('device-snapshot-v1:'+raw).encode(),hashlib.sha256).hexdigest()
        elif envelope['version']==2 and envelope.get('encoding')=='zlib-base64':
            signed={key:value for key,value in envelope.items() if key!='signature'}
            expected=_signed_envelope(signed,token)
        else: raise ValueError()
        if envelope['source']!=source_id(token) or not hmac.compare_digest(envelope['signature'],expected): raise ValueError()
        if envelope.get('version',1)==2:
            packed=base64.b64decode(envelope['payload'],validate=True)
            if len(packed)>MAX_SNAPSHOT_BYTES: raise ValueError()
            decompressor=zlib.decompressobj()
            raw_bytes=decompressor.decompress(packed,MAX_SNAPSHOT_BYTES+1)
            # Reject oversized, truncated, concatenated and trailing streams.
            if len(raw_bytes)>MAX_SNAPSHOT_BYTES or decompressor.unconsumed_tail or not decompressor.eof or decompressor.unused_data: raise ValueError()
            raw=raw_bytes.decode('utf-8')
        return decode(json.loads(raw))
    except (ValueError,KeyError,TypeError,AttributeError,zlib.error):
        raise SnapshotError('Не удалось проверить сохранённый снимок. Данные будут загружены из Моего Склада заново.') from None


def save_request(state,token,frames,saved_at,interval=30):
    state['_device_command']={'operation':'save','request_id':uuid.uuid4().hex,'token':token,
        'snapshot_json':seal_snapshot(frames,saved_at,token),'interval':interval}
    state['device_pending']=True
    state['sync_device_saved']=False
    state.pop('device_error',None)


def forget_request(state):
    state['_device_command']={'operation':'forget','request_id':uuid.uuid4().hex}
    state['device_pending']=True
    state['sync_device_saved']=False


def render_and_restore(state,user_id,today):
    if '_device_command' not in state:
        state['_device_command']={'operation':'load','request_id':uuid.uuid4().hex}
    command=state['_device_command']
    component=components.declare_component('remember_connection_fast',path=str(Path(__file__).parent/'browser_vault'))
    result=component(owner=user_id,**command,key='device_vault',default=None)
    # The browser replaces a restore payload by a tiny ack so Streamlit does
    # not resend megabytes of snapshot data with every widget interaction.
    if command['operation']=='idle': return
    if not isinstance(result,dict) or result.get('owner')!=user_id or result.get('request_id')!=command['request_id']: return
    event=(result.get('request_id'),result.get('status'))
    if state.get('_device_handled')==event: return
    state['_device_handled']=event
    state['device_ready']=True
    state['_device_command']={'operation':'idle','request_id':uuid.uuid4().hex}
    state['device_pending']=False
    status=result.get('status')
    if status=='error':
        state['device_error']='Браузер не смог сохранить или открыть подключение. Разрешите хранение данных для этого сайта; обычное подключение продолжает работать.'
    elif status=='saved':
        state['sync_device_saved']=True
        state.pop('device_error',None)
    elif status=='forgotten':
        state['sync_device_saved']=False
        state.pop('device_error',None)
    elif status=='restored' and not state.get('sync_disconnected') and not state.get('_device_ignore_restore'):
        token=result.get('token')
        if not isinstance(token,str) or not token.strip(): return
        token=token.strip()
        state.update(sync_token=token,sync_origin='device',sync_device_saved=True)
        interval=result.get('interval',30)
        if 'sync_interval' not in state: state['sync_interval']=interval if interval in [0,15,30,60] else 30
        if 'live_data' not in state and result.get('snapshot_json'):
            try:
                frames,saved_at=unseal_snapshot(result['snapshot_json'],token)
                assign(state,frames,today,saved_at,restored=True)
                state['sync_attempt_at']=saved_at
                state['sync_resume_after']=time.time()+60
                # Upgrade a large legacy browser record without querying API.
                if len(result['snapshot_json'].encode())>=COMPRESSION_THRESHOLD or json.loads(result['snapshot_json']).get('transport')=='zlib-base64':
                    save_request(state,token,frames,saved_at,state.get('sync_interval',30))
            except SnapshotError:
                state['device_error']='Ключ восстановлен, но снимок устарел или повреждён. Выполняется новая загрузка.'
        if 'live_data' not in state: state['device_needs_load']=True
