"""Session polling and restore after restart, with credentials supplied by hosting."""
import time
from .live_data import load_live
from .analytics import client_summary
from .recommendations import generate
from .storage import StoreError
from .snapshots import SnapshotError


def due(state,interval,now=None):
    current=now if now is not None else time.time()
    return bool(interval and state.get('sync_token') and current>=state.get('sync_resume_after',0) and current>=state.get('sync_attempt_at',0)+interval*60)


def assign(state,frames,today,saved_at,restored=False):
    summary=client_summary(frames[0],frames[2],today)
    recs=generate(summary,frames[2],frames[1],today)
    state.update(live_data=frames,live_analytics=(summary,recs),sync_success_at=saved_at,sync_restored=restored)
    state.pop('live_error',None)


def restore(state,today,cache):
    snapshot=cache.load()
    if snapshot is None: return False
    frames,saved_at=snapshot
    assign(state,frames,today,saved_at,restored=True)
    state.pop('sync_cache_error',None)
    # Show the saved snapshot immediately; the next refresh waits for the timer.
    state['sync_attempt_at']=saved_at
    state['sync_resume_after']=time.time()+60
    return True


def refresh(state,today,token=None,progress=None,retain=False,cache=None):
    state['sync_attempt_at']=time.time()
    fresh=load_live(today,token=token or state.get('sync_token'),progress=progress)
    saved_at=time.time()
    assign(state,fresh,today,saved_at)
    state.pop('sync_cache_error',None)
    state.pop('sync_resume_after',None)
    if cache is not None:
        try: cache.save(fresh,saved_at)
        except (StoreError,SnapshotError): state['sync_cache_error']='Данные загружены, но снимок не сохранён. При перезапуске потребуется повторная автоматическая выгрузка.'
    if retain and token: state['sync_token']=token
    elif token: state.pop('sync_token',None)
    return fresh
