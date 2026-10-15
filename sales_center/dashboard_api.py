"""Small read-only CRM refresh: counterparties and owners, no shipment reads."""
import time
from .activity_api import ClientActivityClient
from .moysklad import MoySkladError
from .dashboard_data import merge_counterparties,reference_id


def load_counterparties(token,clients,progress=None):
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
        return merge_counterparties(clients,counterparties,employees,time.time())
    except (KeyError,TypeError,ValueError,OverflowError):
        raise MoySkladError('Не удалось обработать список контрагентов. Прежние данные сохранены.') from None
    finally: api.session.close()
