"""Read-only JSON API client: no persisted credentials, writes or arbitrary URLs."""
import os
import re
import requests

class MoySkladError(RuntimeError):
    pass

class MoySkladClient:
    BASE = 'https://api.moysklad.ru/api/remap/1.2'
    ENTITIES = {'counterparty', 'assortment', 'demand', 'currency'}
    def __init__(self, token=None):
        token = (token or os.environ.get('MOYSKLAD_TOKEN') or '').strip()
        if not token:
            raise MoySkladError('Введите API-токен в поле подключения или задайте MOYSKLAD_TOKEN в окружении.')
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'})
    def _get(self, path, params):
        try:
            r = self.session.get(f'{self.BASE}/{path}',params=params,timeout=30,allow_redirects=False)
            if r.status_code in (401,403):
                raise MoySkladError('Мой Склад отклонил доступ. Проверьте ключ, права чтения и сетевой доступ.')
            if r.status_code == 429:
                raise MoySkladError('Достигнут лимит API. Повторите загрузку позже.')
            if 300 <= r.status_code < 400:
                raise MoySkladError('API вернул неожиданный переход. Загрузка остановлена.')
            r.raise_for_status()
            payload = r.json()
            if not isinstance(payload,dict) or not isinstance(payload.get('rows'),list):
                raise MoySkladError('API вернул неожиданный формат данных.')
            return payload
        except (requests.RequestException,ValueError):
            raise MoySkladError('Не удалось получить данные Моего Склада. Проверьте сеть и доступность API.') from None
    def _all(self, path, params=None):
        params = dict(params or {})
        rows,offset = [],0
        # Safety cap: never silently return a truncated dataset.
        for _ in range(1000):
            page = self._get(path,{**params,'limit':100,'offset':offset})
            batch = page['rows']
            rows.extend(batch)
            offset += len(batch)
            if len(batch) < 100 or offset >= page.get('meta',{}).get('size',float('inf')):
                return rows
        raise MoySkladError('Объём данных превышает лимит MVP. Загрузка остановлена без частичного результата.')
    def list_entities(self,entity,params=None):
        if entity not in self.ENTITIES:
            raise ValueError('Неподдерживаемая сущность.')
        return self._all(f'entity/{entity}',params)
    def demand_positions(self,doc_id):
        if not re.fullmatch(r'[a-fA-F0-9-]{36}',doc_id):
            raise MoySkladError('Неожиданный идентификатор отгрузки.')
        return self._all(f'entity/demand/{doc_id}/positions',{'expand':'assortment','fields':'stock'})
