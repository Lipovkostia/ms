"""CRM refresh with optional document summaries; never read line positions."""
import time
import pandas as pd
from .activity_api import ClientActivityClient
from .moysklad import MoySkladError
from .dashboard_data import merge_counterparties,reference_id


def load_counterparties(token,clients,progress=None,include_activity=False,today=None):
    api=ClientActivityClient(token)
    def read(entity,label,params=None):
        if progress: progress(label)
        rows=api.list_entities(entity,params,progress=(lambda n,t:progress(label,n,t)) if progress else None)
        if any(not isinstance(row,dict) for row in rows): raise ValueError()
        return rows
    try:
        active=read('counterparty','Обновление контрагентов')
        archived=read('counterparty','Обновление архивных контрагентов',{'filter':'archived=true'})
        # Repeated records can appear when an archive status changes mid-read.
        # Reject the inconsistent refresh instead of silently accepting a subset.
        counterparties=active+archived
        if len({reference_id(c) for c in counterparties})!=len(counterparties):
            raise MoySkladError('Контрагенты изменились во время загрузки. Повторите обновление; прежние данные сохранены.')
        employees=read('employee','Обновление владельцев-сотрудников')
        result=merge_counterparties(clients,counterparties,employees,time.time())
        if include_activity:
            from .client_segments import enrich
            from .dashboard_workspace import attach_orders
            today=today or pd.Timestamp.now(tz='Europe/Moscow').date()
            currencies={reference_id(c):c for c in read('currency','Проверка валют сделок')}
            shipments=read('demand','Обновление итогов покупок',{'filter':'applicable=true'})
            for doc in shipments:
                if doc.get('agent',{}).get('meta',{}).get('type')=='organization': continue
                currency=currencies.get(reference_id(doc.get('rate',{}).get('currency') or {}),{})
                if str(currency.get('isoCode')).upper() not in {'643','RUB'}:
                    raise MoySkladError('В истории покупок есть неизвестная или другая валюта. Прежние данные сохранены.')
            orders=read('customerorder','Обновление заказов покупателей')
            present=result.dashboard_loaded.fillna(False).eq(True)
            refreshed=enrich(result[present].copy(),counterparties,employees,shipments,orders,today)
            refreshed=attach_orders(refreshed,orders,today)
            attrs=result.attrs.copy()
            result=pd.concat([refreshed,result[~present]],ignore_index=True) if (~present).any() else refreshed
            result.attrs.update(attrs)
        return result
    except (KeyError,TypeError,ValueError,OverflowError):
        raise MoySkladError('Не удалось обработать список контрагентов. Прежние данные сохранены.') from None
    finally: api.session.close()
