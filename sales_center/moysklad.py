"""Read-only JSON API client: no persisted credentials, writes or arbitrary URLs."""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
import requests

class MoySkladError(RuntimeError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable

class MoySkladClient:
    BASE = 'https://api.moysklad.ru/api/remap/1.2'
    ENTITIES = {'counterparty', 'assortment', 'demand', 'currency', 'employee', 'customerorder'}
    def __init__(self, token=None):
        token = (token or os.environ.get('MOYSKLAD_TOKEN') or '').strip()
        if not token:
            raise MoySkladError('Введите API-токен в поле подключения или задайте MOYSKLAD_TOKEN в окружении.')
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'})
    def _get(self, path, params, session=None):
        for attempt in range(2):
            try:
                return self._get_once(path,params,session=session)
            except MoySkladError as exc:
                if not exc.retryable or attempt == 1:
                    raise
                time.sleep(1)

    def _get_once(self, path, params, session=None):
        try:
            r = (session or self.session).get(f'{self.BASE}/{path}',params=params,timeout=(10,90),allow_redirects=False)
            if r.status_code in (401,403):
                raise MoySkladError('Мой Склад отклонил доступ. Проверьте ключ, права чтения и сетевой доступ.')
            if r.status_code == 429:
                raise MoySkladError('Достигнут лимит API. Повторите загрузку позже.',retryable=True)
            if 300 <= r.status_code < 400:
                raise MoySkladError('API вернул неожиданный переход. Загрузка остановлена.')
            if r.status_code >= 400:
                try:
                    codes = ', '.join(str(e.get('code','?')) for e in r.json().get('errors',[]))
                except (ValueError, AttributeError):
                    codes = '?'
                raise MoySkladError(f'API отклонил запрос: HTTP {r.status_code}, код {codes}. Повторите загрузку или проверьте права доступа.',retryable=r.status_code in {500,502,503,504})
            r.raise_for_status()
            payload = r.json()
            if not isinstance(payload,dict) or not isinstance(payload.get('rows'),list):
                raise MoySkladError('API вернул неожиданный формат данных.')
            return payload
        except requests.exceptions.SSLError:
            raise MoySkladError('Не удалось проверить защищённое соединение с API. Проверьте сертификаты и сеть.') from None
        except (requests.Timeout,requests.ConnectionError) as exc:
            raise MoySkladError(f'Временный сбой связи с API ({type(exc).__name__}). Повторите загрузку.',retryable=True) from None
        except (requests.RequestException,ValueError):
            raise MoySkladError('Не удалось получить данные Моего Склада. Проверьте сеть и доступность API.') from None
    def _parallel_page(self, path, params):
        # Each worker owns its session; no shared mutable requests state.
        with requests.Session() as session:
            session.headers.update(self.session.headers)
            return self._get(path, params, session=session)

    def _all(self, path, params=None, progress=None):
        params = dict(params or {})
        rows,offset = [],0
        limit = 100 if params.get('expand') or params.get('fields') == 'stock' else 1000
        # Safety cap: never silently return a truncated dataset.
        for _ in range(1000):
            page = self._get(path,{**params,'limit':limit,'offset':offset})
            batch = page['rows']
            rows.extend(batch)
            offset += len(batch)
            if offset > 100000:
                raise MoySkladError('Объём данных превышает лимит MVP: 100 000 записей на коллекцию.')
            if progress:
                progress(offset, page.get('meta',{}).get('size',offset))
            total = page.get('meta',{}).get('size')
            if total is not None and total > 100000:
                raise MoySkladError('Объём данных превышает лимит MVP: 100 000 записей на коллекцию.')
            if len(batch) < limit or offset >= (total if total is not None else float('inf')):
                return rows
            if path == 'entity/demand' and total is not None:
                offsets = range(offset,total,limit)
                with ThreadPoolExecutor(max_workers=2) as pool:
                    pages = pool.map(lambda off: self._parallel_page(path,{**params,'limit':limit,'offset':off}),offsets)
                    for off,result in zip(offsets,pages):
                        batch = result['rows']
                        if len(batch) != min(limit,total-off):
                            raise MoySkladError('Отгрузки изменились во время загрузки. Повторите подключение.')
                        rows.extend(batch)
                        if progress:
                            progress(len(rows),total)
                return rows
        raise MoySkladError('Объём данных превышает лимит MVP. Загрузка остановлена без частичного результата.')
    def list_entities(self,entity,params=None,progress=None):
        if entity not in self.ENTITIES:
            raise ValueError('Неподдерживаемая сущность.')
        return self._all(f'entity/{entity}',params,progress=progress)
    def demand_positions(self,doc_id):
        if not re.fullmatch(r'[a-fA-F0-9-]{36}',doc_id):
            raise MoySkladError('Неожиданный идентификатор отгрузки.')
        return self._all(f'entity/demand/{doc_id}/positions',{'expand':'assortment','fields':'stock'})
