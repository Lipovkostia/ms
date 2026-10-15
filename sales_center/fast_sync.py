"""Nonblocking, session-owned API refresh; workers never access Streamlit state."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import BoundedSemaphore, Lock
import time
from .snapshots import source_id, SnapshotError
from .storage import StoreError
from .moysklad import MoySkladError
from .sync import restore, due

_POOL=ThreadPoolExecutor(max_workers=2,thread_name_prefix='moysklad-refresh')
_SLOTS=BoundedSemaphore(4)


@dataclass
class Progress:
    stage: str='Ожидание обновления'
    count: int=0
    total: int=0
    lock: object=field(default_factory=Lock,repr=False)
    def report(self,stage,count=0,total=0):
        with self.lock: self.stage,self.count,self.total=stage,int(count),int(total)
    def text(self):
        with self.lock:
            return f'{self.stage}: {self.count:,} / {self.total:,}' if self.total else self.stage


@dataclass
class Job:
    source: str
    owner: str
    future: object
    progress: Progress
    origin: str
    remember: bool
    kind: str='full'


def _read(today,token,cache,progress,kind,base_frames,base_saved_at):
    try:
        # Resolve the existing entry point at execution time; tests and adapters
        # keep one API boundary. No session_state or UI calls in this worker.
        from . import sync
        from .analytics import client_summary
        from .recommendations import generate
        if kind=='catalog':
            from .price_catalog import load_catalog
            progress.report('Обновление товаров и цен')
            frames=(base_frames[0],load_catalog(token),base_frames[2])
        elif kind=='counterparties':
            from .dashboard_api import load_counterparties
            frames=(load_counterparties(token,base_frames[0],progress.report),base_frames[1],base_frames[2])
        else:
            frames=sync.load_live(today,token=token,progress=progress.report)
        if not frames[0].attrs.get('account_id'):
            raise MoySkladError('API не вернул accountId. Обновление отменено; прежние данные сохранены.')
        progress.report('Подготовка аналитики')
        summary=client_summary(frames[0],frames[2],today)
        analytics=(summary,generate(summary,frames[2],frames[1],today))
        saved_at=base_saved_at if kind in {'catalog','counterparties'} else time.time()
        warning=None
        if cache is not None:
            try: cache.save(frames,saved_at)
            except (StoreError,SnapshotError): warning='Данные обновлены, но серверный снимок не сохранён. Копия браузера продолжает использоваться.'
        return frames,analytics,saved_at,warning
    except (KeyError,TypeError,ValueError,OverflowError):
        raise MoySkladError('Не удалось обработать ответ Моего Склада. Прежние данные сохранены; повторите обновление.') from None
    finally: _SLOTS.release()


def start(state,today,token,owner,cache=None,origin=None,remember=None,kind='full'):
    """Start once for this session/source, without waiting on API or CPU work."""
    if kind not in {'full','catalog','counterparties'}: raise ValueError('Неподдерживаемый вид обновления.')
    if kind!='full' and 'live_data' not in state: raise MoySkladError('Сначала подключите Мой Склад.')
    token=token.strip()
    if not token: raise MoySkladError('Для обновления сначала подключите Мой Склад.')
    digest=source_id(token)
    previous=state.get('live_refresh_job')
    if previous and previous.source==digest and previous.owner==owner: return False
    if not _SLOTS.acquire(blocking=False):
        state['live_error']='Сервер уже обновляет данные. Сохранённая база доступна; повторите обновление позже.'
        return False
    if previous and previous.future.cancel(): _SLOTS.release()
    progress=Progress()
    try: future=_POOL.submit(_read,today,token,cache,progress,kind,state.get('live_data'),state.get('sync_success_at',time.time()))
    except RuntimeError:
        _SLOTS.release()
        state['live_error']='Не удалось запустить обновление. Сохранённые данные доступны.'
        return False
    state['live_refresh_job']=Job(digest,owner,future,progress,origin or state.get('sync_origin','manual'),state.get('sync_device_saved',False) if remember is None else remember,kind)
    state['sync_pending_token']=token
    if kind=='full': state['sync_attempt_at']=time.time()
    state.pop('live_error',None)
    return True


def pending(state): return state.get('live_refresh_job') is not None


def finish(state,owner):
    """Atomically publish only the current session's matching completed source."""
    job=state.get('live_refresh_job')
    if job is None or not job.future.done(): return False
    state.pop('live_refresh_job',None)
    token=state.pop('sync_pending_token','')
    if job.owner!=owner or job.source!=source_id(token): return False
    try: frames,analytics,saved_at,warning=job.future.result()
    except MoySkladError as exc:
        state['live_error']=str(exc)
        return False
    except Exception:
        # Worker exception details may contain upstream data. Never expose them.
        state['live_error']='Не удалось завершить обновление. Прежние данные сохранены; попробуйте ещё раз.'
        return False
    state.update(live_data=frames,live_analytics=analytics,sync_success_at=saved_at,sync_restored=False,sync_token=token,sync_origin=job.origin,sync_disconnected=False)
    state.pop('live_error',None)
    state.pop('sync_resume_after',None)
    if warning: state['sync_cache_error']=warning
    else: state.pop('sync_cache_error',None)
    if job.kind=='catalog': state['sync_catalog_at']=time.time()
    if job.kind=='counterparties': state['sync_counterparties_at']=time.time()
    if job.remember: state['device_save_after_refresh']=True
    elif job.origin!='device': state['sync_device_saved']=False
    return True
