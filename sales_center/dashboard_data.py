"""Counterparty creation metadata and pure Dashboard filters (no purchase dates)."""
from urllib.parse import urlsplit
import pandas as pd
from .moysklad import MoySkladError

EMPTY='Не указан'
NO_OWNER='Не назначен'
FIELDS=['created_at','code','owner_employee','owner_employee_id','crm_project','crm_archived',
        'crm_project_field_present','dashboard_loaded','dashboard_synced_at']


def reference_id(value):
    return value.get('id') or urlsplit(value.get('meta',{}).get('href','')).path.rstrip('/').split('/')[-1]


def project_value(counterparty):
    # Project is not a standard Counterparty property in Remap 1.2. Read only
    # the explicitly named custom field, never infer it from orders or tags.
    for attribute in counterparty.get('attributes') or []:
        if str(attribute.get('name','')).strip().casefold() in {'проект','project'}:
            value=attribute.get('value')
            if value is None or value=='': return '',True
            if isinstance(value,str): return value.strip(),True
            if isinstance(value,dict): return str(value.get('name') or 'Название проекта недоступно'),True
            return 'Формат проекта не поддерживается',True
    return '',False


def metadata(counterparties,employees=(),synced_at=None):
    from .live_data import local_id
    people={reference_id(e):e.get('name') or e.get('fullName') or 'Сотрудник без имени' for e in employees}
    rows=[]
    for c in counterparties:
        owner=c.get('owner') or {}
        owner_id=reference_id(owner)
        project,present=project_value(c)
        created=c.get('created')
        if created:
            try:
                date=pd.Timestamp(created)
                if pd.isna(date): raise ValueError()
                if date.tzinfo is not None: date=date.tz_convert('Europe/Moscow').tz_localize(None)
                created=date.isoformat()
            except (ValueError,TypeError,OverflowError):
                raise MoySkladError('У контрагента некорректная дата создания. Прежний список сохранён.') from None
        rows.append(dict(client_id=local_id(reference_id(c)),created_at=created or None,
            code=str(c.get('code') or '').strip(),owner_employee_id=owner_id,
            owner_employee=people.get(owner_id) or owner.get('name') or ('Сотрудник недоступен' if owner_id else NO_OWNER),
            crm_project=project,crm_archived=bool(c.get('archived',False)),crm_project_field_present=present,
            dashboard_loaded=True,dashboard_synced_at=synced_at))
    result=pd.DataFrame(rows,columns=['client_id',*FIELDS])
    if result.client_id.duplicated().any():
        raise MoySkladError('Список контрагентов содержит повторные идентификаторы. Прежние данные сохранены.')
    return result


def attach(clients,counterparties,employees=(),synced_at=None):
    extra=metadata(counterparties,employees,synced_at).set_index('client_id')
    result=clients.copy()
    for field in FIELDS:
        result[field]=result.client_id.map(extra[field])
    return result


def merge_counterparties(clients,counterparties,employees,synced_at):
    """Refresh CRM details without rewriting shipment history or financials."""
    from .live_data import local_id
    expected=clients.attrs.get('account_id')
    accounts={c.get('accountId') for c in counterparties}
    if not expected or (accounts and accounts!={expected}):
        raise MoySkladError('Аккаунт контрагентов не совпадает с сохранённой базой. Прежние данные сохранены.')
    records={int(row['client_id']):row for row in clients.to_dict('records')}
    for row in records.values(): row['dashboard_loaded']=False
    for c in counterparties:
        cid=local_id(reference_id(c))
        if cid not in records:
            records[cid]=dict(client_id=cid,segment='Не указан')
            for field,default in [('purchase_history',[]),('recent_order_dates',[]),('crm_history_loaded',False)]:
                if field in clients: records[cid][field]=default
        records[cid].update(company=c.get('name') or 'Без названия',phone=c.get('phone') or '',
            email=c.get('email') or '',city=c.get('actualAddress') or 'Не указан')
    result=pd.DataFrame(records.values())
    result.attrs.update(clients.attrs)
    return attach(result,counterparties,employees,synced_at)


def listing(clients,include_archived=False):
    required={'client_id','company',*FIELDS}
    if not required.issubset(clients.columns): return pd.DataFrame()
    frame=clients[clients.dashboard_loaded.fillna(False).eq(True)].copy()
    if not include_archived: frame=frame[~frame.crm_archived.fillna(False).astype(bool)]
    frame['created_at']=pd.to_datetime(frame.created_at,errors='coerce',format='mixed')
    for field,empty in [('code',EMPTY),('crm_project',EMPTY),('owner_employee',NO_OWNER)]:
        frame[field]=frame[field].fillna('').astype(str).str.strip().replace('',empty)
    return frame


def select(frame,start=None,end=None,owners=(),projects=(),codes=(),query='',oldest_first=False):
    result=frame.copy()
    if start is not None: result=result[result.created_at>=pd.Timestamp(start)]
    if end is not None: result=result[result.created_at<pd.Timestamp(end)+pd.Timedelta(days=1)]
    for field,values in [('owner_employee',owners),('crm_project',projects),('code',codes)]:
        if values: result=result[result[field].isin(values)]
    if query.strip(): result=result[result.company.str.contains(query.strip(),case=False,regex=False,na=False)]
    return result.sort_values(['created_at','company','client_id'],ascending=[oldest_first,True,True],na_position='last',kind='stable')
