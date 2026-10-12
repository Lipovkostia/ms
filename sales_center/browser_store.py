"""Browser-local encrypted persistence; secrets never enter server records or Git."""
from pathlib import Path
import hashlib
import hmac
import json
import time
import uuid
import streamlit.components.v1 as components
from .snapshots import encode,decode,SnapshotError,source_id
from .sync import assign


def seal_snapshot(frames,saved_at,token):
    raw=json.dumps(encode(frames,saved_at),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    signature=hmac.new(token.encode(),('device-snapshot-v1:'+raw).encode(),hashlib.sha256).hexdigest()
    return json.dumps({'source':source_id(token),'payload':raw,'signature':signature},ensure_ascii=False)


def unseal_snapshot(text,token):
    try:
        envelope=json.loads(text)
        raw=envelope['payload']
        expected=hmac.new(token.encode(),('device-snapshot-v1:'+raw).encode(),hashlib.sha256).hexdigest()
        if envelope['source']!=source_id(token) or not hmac.compare_digest(envelope['signature'],expected): raise ValueError()
        return decode(json.loads(raw))
    except (ValueError,KeyError,TypeError,AttributeError):
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
    component=components.declare_component('remember_connection',path=str(Path(__file__).parent/'browser_vault'))
    result=component(owner=user_id,**command,key='device_vault',default=None)
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
            except SnapshotError:
                state['device_error']='Ключ восстановлен, но снимок устарел или повреждён. Выполняется новая загрузка.'
        if 'live_data' not in state: state['device_needs_load']=True
