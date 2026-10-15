"""Client activity from all available posted shipments, not catalogue line counts."""
import pandas as pd
from .live_data import external_id, number
from .moysklad import MoySkladError

DEFAULT_BLOCKS=[dict(name='Текущие',start=0,end=30,minimum=2),dict(name='Остывающие',start=30,end=60,minimum=1),dict(name='Уходящие',start=60,end=90,minimum=1),dict(name='Потерянные',start=90,end=365,minimum=1)]


def enrich(clients, counterparties, employees, shipments, new_orders, today):
    people={external_id(e):e.get('name') or e.get('fullName') or 'Сотрудник без имени' for e in employees}
    cp={external_id(c):c for c in counterparties}
    history={}
    seen=set()
    for doc in shipments:
        if doc.get('positions',{}).get('meta',{}).get('size')==0: continue
        if not doc.get('applicable') or doc.get('agent',{}).get('meta',{}).get('type')=='organization': continue
        if doc['id'] in seen: raise MoySkladError('Повторный идентификатор отгрузки. Повторите обновление.')
        seen.add(doc['id'])
        cid=external_id(doc.get('agent') or {})
        if cid not in cp: raise MoySkladError('История содержит недоступного контрагента. Проверьте права чтения.')
        history.setdefault(cid,[]).append(dict(date=pd.Timestamp(doc['moment']).isoformat(),amount=number(doc,'sum')/100))
    recent={}
    threshold=pd.Timestamp(today)-pd.Timedelta(days=10)
    for doc in new_orders:
        created=doc.get('created')
        if not created: continue
        timestamp=pd.Timestamp(created)
        if threshold<=timestamp<pd.Timestamp(today)+pd.Timedelta(days=1):
            cid=external_id(doc.get('agent') or {})
            recent.setdefault(cid,[]).append(timestamp.isoformat())
    result=clients.copy()
    from .live_data import local_id
    by_id={local_id(cid):cid for cid in cp}
    result['purchase_history']=[history.get(by_id[row],[]) for row in result.client_id]
    result['owner_employee']=[people.get(external_id(cp[by_id[row]].get('owner') or {}),'Не назначен') for row in result.client_id]
    result['recent_order_dates']=[recent.get(by_id[row],[]) for row in result.client_id]
    result['crm_history_loaded']=True
    from .dashboard_data import attach
    import time
    return attach(result,counterparties,employees,time.time())


def activity(clients,today):
    rows=[]; day=pd.Timestamp(today).normalize()
    for c in clients.to_dict('records'):
        history=c.get('purchase_history',[]) or []
        dates=pd.to_datetime([item['date'] for item in history])
        dates=dates[dates<=day+pd.Timedelta(days=1)-pd.Timedelta(microseconds=1)]
        last=dates.max() if len(dates) else pd.NaT
        recent=[pd.Timestamp(d) for d in c.get('recent_order_dates',[]) or []]
        rows.append(dict(client_id=c['client_id'],company=c['company'],owner_employee=c.get('owner_employee','Не назначен'),last_purchase=last,days_since=(day-last.normalize()).days if len(dates) else None,purchase_count=len(dates),total_amount=sum(item['amount'] for item in history if pd.Timestamp(item['date'])<day+pd.Timedelta(days=1)),purchase_dates=dates,recent_orders=sum(day-pd.Timedelta(days=10)<=d<day+pd.Timedelta(days=1) for d in recent)))
    return pd.DataFrame(rows)


def select_block(frame,block,today):
    day=pd.Timestamp(today).normalize()
    # Half-open ranges prevent duplicate membership at 30/60/90 days.
    result=frame[(frame.days_since>=block['start'])&(frame.days_since<block['end'])].copy()
    result['window_purchases']=[sum(day-pd.Timedelta(days=block['end'])<d.normalize()<=day-pd.Timedelta(days=block['start']) for d in dates) for dates in result.purchase_dates]
    result=result[result.window_purchases>=block['minimum']]
    return result.sort_values(['recent_orders','total_amount'],ascending=[False,False])


def load_client_activity(token,clients,today):
    """Compatibility entry point for integrations importing the former module."""
    from .activity_api import load_client_activity as load_activity
    return load_activity(token,clients,today)
