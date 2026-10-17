"""Auditable manager signals from CRM documents and the current user's tasks."""
import time
import pandas as pd
from .dashboard_data import listing,reference_id,NO_OWNER
from .moysklad import MoySkladError

VIEWS={'all':'Вся база','new':'Новые · 30 дней','attention':'Взять в работу',
       'deals':'Есть сделки','due':'Контакты сегодня','unassigned':'Без менеджера'}


def attach_orders(clients,documents,today,synced_at=None):
    from .live_data import local_id
    known=set(clients.client_id);counts={};latest={};recent={};seen=set()
    end=pd.Timestamp(today)+pd.Timedelta(days=1)
    for doc in documents:
        if doc.get('agent',{}).get('meta',{}).get('type')=='organization': continue
        oid=reference_id(doc)
        if not oid or oid in seen: raise MoySkladError('Повторный или отсутствующий идентификатор заказа. Прежние данные сохранены.')
        seen.add(oid)
        if doc.get('accountId') and doc['accountId']!=clients.attrs.get('account_id'):
            raise MoySkladError('Заказ относится к другому аккаунту. Прежние данные сохранены.')
        cid=local_id(reference_id(doc.get('agent') or {}))
        if cid not in known: raise MoySkladError('Контрагент заказа недоступен. Проверьте права чтения.')
        counts[cid]=counts.get(cid,0)+1
        if doc.get('created'):
            stamp=pd.Timestamp(doc['created'])
            if pd.isna(stamp): raise ValueError('created')
            if stamp.tzinfo: stamp=stamp.tz_convert('Europe/Moscow').tz_localize(None)
            latest[cid]=max(stamp,latest.get(cid,stamp))
            if end-pd.Timedelta(days=11)<=stamp<end: recent[cid]=recent.get(cid,0)+1
    result=clients.copy()
    result['crm_order_count']=result.client_id.map(counts).fillna(0).astype('int64')
    result['crm_last_order_created']=result.client_id.map({cid:d.isoformat() for cid,d in latest.items()})
    result['crm_recent_order_count']=result.client_id.map(recent).fillna(0).astype('int64')
    result['crm_orders_loaded']=True
    result['crm_activity_synced_at']=synced_at if synced_at is not None else time.time()
    return result


def client_facts(clients,today):
    """One preparation per snapshot; tasks are joined separately on each render."""
    frame=listing(clients,include_archived=True)
    if frame.empty: return frame
    day=pd.Timestamp(today).normalize()
    frame['history_known']=frame.get('crm_history_loaded',pd.Series(False,index=frame.index)).fillna(False).astype(bool)
    frame['orders_known']=frame.get('crm_orders_loaded',pd.Series(False,index=frame.index)).fillna(False).astype(bool)
    history=[]
    for row in frame.to_dict('records'):
        if row['history_known']:
            for item in row.get('purchase_history',[]) or []:
                history.append((row['client_id'],item['date'],item['amount']))
    docs=pd.DataFrame(history,columns=['client_id','date','amount'])
    docs['date']=pd.to_datetime(docs.date,format='mixed')
    docs=docs[docs.date<day+pd.Timedelta(days=1)]
    totals=docs.groupby('client_id').agg(purchases=('amount','size'),turnover=('amount','sum'),last_purchase=('date','max'))
    for field in ['purchases','turnover','last_purchase']: frame[field]=frame.client_id.map(totals[field])
    for field in ['purchases','turnover']: frame.loc[frame.history_known,field]=frame.loc[frame.history_known,field].fillna(0)
    frame['last_purchase']=pd.to_datetime(frame.last_purchase)
    frame['days_since']=(day-frame.last_purchase.dt.normalize()).dt.days
    cycle_docs=docs[docs.date>=day-pd.DateOffset(months=12)].sort_values(['client_id','date']).copy()
    cycle_docs['gap']=cycle_docs.groupby('client_id').date.diff().dt.total_seconds()/86400
    cycles=cycle_docs.groupby('client_id').gap.agg(['median','count'])
    frame['cycle']=frame.client_id.map(cycles['median'].where(cycles['count']>=2))
    frame['cycle_late']=frame.cycle.gt(0)&frame.days_since.gt(frame.cycle*1.5)
    frame['orders']=pd.to_numeric(frame.get('crm_order_count',pd.Series(index=frame.index,dtype=float)),errors='coerce').where(frame.orders_known)
    # Recompute recent from the last creation date so a cached snapshot ages correctly.
    last_order=pd.to_datetime(frame.get('crm_last_order_created',pd.Series(index=frame.index,dtype=object)),format='mixed',errors='coerce')
    frame['recent_order']=last_order.ge(day-pd.Timedelta(days=10))&last_order.lt(day+pd.Timedelta(days=1))
    frame['is_new']=frame.created_at.ge(day-pd.Timedelta(days=29))&frame.created_at.lt(day+pd.Timedelta(days=1))
    frame['unassigned']=frame.owner_employee.eq(NO_OWNER)
    frame['has_deals']=frame.orders.gt(0)|frame.purchases.gt(0)
    return frame


def with_tasks(frame,tasks,today):
    """Task absence refers only to this user's scoped task list, never the team."""
    result=frame.copy()
    if result.empty: return result
    day=pd.Timestamp(today).normalize()
    active=tasks[~tasks.status.isin(['Выполнена','Отменена'])].copy() if not tasks.empty else tasks.copy()
    if not active.empty:
        active['due_date']=pd.to_datetime(active.due,errors='coerce')
        active=active.sort_values(['due_date','id'],na_position='last').drop_duplicates('client_id')
        contacts=active.set_index('client_id').due_date
    else: contacts=pd.Series(dtype='datetime64[ns]')
    result['next_contact']=pd.to_datetime(result.client_id.map(contacts))
    result['has_task']=result.client_id.isin(active.client_id if not active.empty else [])
    result['contact_due']=result.next_contact.le(day)
    statuses=[];reasons=[];ranks=[];attention=[]
    for c in result.itertuples():
        needs=True
        if c.contact_due:
            late=(day-c.next_contact).days
            status='Просрочен контакт' if late else 'Связаться сегодня'
            reason=f'Ваша открытая задача просрочена на {late} дн.' if late else 'На сегодня назначена ваша задача.'
            rank=0 if late else 1
        elif c.unassigned:
            status,reason,rank='Нет менеджера','В Моём Складе не назначен владелец-сотрудник.',2
        elif c.has_task:
            status,reason,rank,needs='В работе','У вас уже есть открытая задача по этому клиенту.',8,False
        elif c.recent_order:
            status,reason,rank='Новый заказ','В базе есть заказ, созданный за последние 10 дней. Проверьте его состояние.',3
        elif c.cycle_late:
            status,reason,rank='Пора повторить заказ',f'Без покупок {c.days_since:.0f} дн.; обычный цикл {c.cycle:.0f} дн. Задержка больше 1,5 цикла.',4
        elif c.purchases==0 and c.orders>0:
            status,reason,rank='Первый заказ','Есть заказ покупателя, но проведённых отгрузок в доступной истории ещё нет. Уточните состояние заказа.',5
        elif c.history_known and c.orders_known and c.purchases==0 and c.orders==0:
            status,reason,rank='Первый контакт','В доступной базе нет заказов и проведённых отгрузок. Подготовьте первое предложение.',6
        elif not c.history_known or not c.orders_known:
            status,reason,rank,needs='Уточнить данные','История загружена не полностью. Обновите CRM и сделки для оценки клиента.',10,False
        else:
            reason='В истории есть проведённые отгрузки. Для оценки обычного цикла пока недостаточно данных.' if pd.isna(c.cycle) or c.cycle<=0 else 'Есть проведённые отгрузки; задержка больше 1,5 обычного цикла не выявлена.'
            status,rank,needs='Есть покупки',9,False
        statuses.append(status);reasons.append(reason);ranks.append(rank);attention.append(needs)
    result['attention_status']=statuses;result['reason']=reasons;result['rank']=ranks;result['attention']=attention
    return result


def subset(frame,view):
    field={'new':'is_new','attention':'attention','deals':'has_deals','due':'contact_due','unassigned':'unassigned'}.get(view)
    return frame[frame[field]] if field else frame


def sort_clients(frame,sort):
    if sort=='Сначала новые': return frame.sort_values(['created_at','client_id'],ascending=[False,True],na_position='last')
    if sort=='Сначала старые': return frame.sort_values(['created_at','client_id'],na_position='last')
    if sort=='По обороту': return frame.sort_values(['turnover','client_id'],ascending=[False,True],na_position='last')
    return frame.sort_values(['rank','next_contact','created_at','client_id'],ascending=[True,True,False,True],na_position='last')
