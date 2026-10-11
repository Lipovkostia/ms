"""Session-local, periodic polling; no background daemon or shared credential cache."""
import time
from .live_data import load_live
from .analytics import client_summary
from .recommendations import generate

def due(state,interval,now=None):
    return bool(interval and state.get('sync_token') and (now if now is not None else time.time()) >= state.get('sync_attempt_at',0)+interval*60)

def refresh(state,today,token=None,progress=None,retain=False):
    state['sync_attempt_at']=time.time()
    fresh=load_live(today,token=token or state.get('sync_token'),progress=progress)
    summary=client_summary(fresh[0],fresh[2],today)
    recs=generate(summary,fresh[2],fresh[1],today)
    state.update(live_data=fresh,live_analytics=(summary,recs),sync_success_at=time.time())
    state.pop('live_error',None)
    if retain and token: state['sync_token']=token
    elif token: state.pop('sync_token',None)
    return fresh
