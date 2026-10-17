"""Dense manager workspace with real documents, scoped tasks and native controls."""
from datetime import timedelta
import hashlib
import inspect
import pandas as pd
import streamlit as st
from .dashboard_data import FIELDS,select
from .dashboard_workspace import VIEWS,client_facts,with_tasks,subset,sort_clients
from .presentation import safe
from .storage import StoreError

SORTS=['Сначала важные','Сначала новые','Сначала старые','По обороту']
PREFERENCE_KEYS=['dashboard_'+name for name in ['from','to','all_dates','owners','projects','codes','search','sort','archived','view','size','page']]


def reset(today):
    st.session_state.update(dashboard_from=today-timedelta(days=29),dashboard_to=today,
        dashboard_all_dates=True,dashboard_owners=[],dashboard_projects=[],dashboard_codes=[],
        dashboard_search='',dashboard_sort=SORTS[0],dashboard_page=1,dashboard_archived=False,
        dashboard_view='all',global_search='')
    close_details()


def close_details():
    st.session_state.pop('dashboard_selected_id',None)
    st.session_state.dashboard_selection_version=st.session_state.get('dashboard_selection_version',0)+1


def _options(label,frame,field,key,placeholder):
    values=sorted(frame[field].unique().tolist(),key=str.casefold)
    if key in st.session_state: st.session_state[key]=[v for v in st.session_state[key] if v in values]
    return st.multiselect(label,values,key=key,placeholder=placeholder)


def _money(value): return f'{value:,.0f} ₽'.replace(',',' ') if pd.notna(value) else '—'
def _count(value): return str(int(value)) if pd.notna(value) else '—'


def detail(row,today,store,on_client):
    cid=int(row.client_id)
    with st.container(border=True,key='dashboard-detail'):
        a,b=st.columns([3,1],vertical_alignment='center')
        with a: st.caption('ВЫБРАННЫЙ КЛИЕНТ')
        with b: st.button('✕',key='dashboard_close',help='Закрыть карточку',on_click=close_details)
        st.subheader(row.company)
        st.markdown(f'**{row.attention_status}**')
        st.info(row.reason)
        st.caption(f'Заказов: {_count(row.orders)} · Покупок: {_count(row.purchases)}')
        st.caption(f'Сумма покупок: {_money(row.turnover)}')
        if row.get('phone'): st.text(str(row.phone))
        if row.get('email'): st.text(str(row.email))
        st.button('Открыть карточку клиента →',key='dashboard_open_client',on_click=on_client,args=(cid,),width='stretch')
        if row.has_task:
            due=pd.Timestamp(row.next_contact).strftime('%d.%m.%Y') if pd.notna(row.next_contact) else 'дата не указана'
            st.success('Есть ваша открытая задача. Контакт: '+due)
            st.caption('Изменить срок или результат можно в разделе «Задачи».')
        elif store is not None:
            with st.form(f'dashboard_contact_{cid}'):
                st.markdown('**Следующий шаг**')
                title=st.text_input('Действие',value='Связаться с клиентом',key=f'dashboard_action_{cid}')
                due=st.date_input('Дата контакта',value=today,key=f'dashboard_due_{cid}',format='DD.MM.YYYY')
                note=st.text_area('Заметка',value=row.reason,height=95,key=f'dashboard_note_{cid}')
                submitted=st.form_submit_button('Взять в работу',type='primary',width='stretch')
                if submitted:
                    try:
                        tasks=store.tasks()
                        existing=tasks[(tasks.client_id==cid)&(~tasks.status.isin(['Выполнена','Отменена']))]
                        if existing.empty: store.add(cid,title,due,note,status='В работе')
                        st.session_state.dashboard_notice='Клиент в работе. Задача доступна в разделе «Задачи».'
                        st.rerun()
                    except (StoreError,ValueError) as exc: st.error(str(exc))
            st.caption('Создаётся ваша задача. Владелец в Моём Складе при этом не меняется.')


def render(clients,today,on_client,refresh_data,refreshing=False,can_refresh=False,global_query='',store=None):
    memory_key='dashboard_preferences:'+str(clients.attrs.get('account_id',''))
    for key,value in st.session_state.get(memory_key,{}).items():
        if key in PREFERENCE_KEYS and key not in st.session_state: st.session_state[key]=value
    def remember():
        st.session_state[memory_key]={key:st.session_state[key] for key in PREFERENCE_KEYS if key in st.session_state}
    with st.container(key='dashboard-workspace'):
        if st.session_state.get('dashboard_notice'): st.success(st.session_state.pop('dashboard_notice'))
        if st.session_state.get('live_error'): st.error(st.session_state.live_error)
        if not set(FIELDS).issubset(clients.columns):
            st.info('Обновите CRM и сделки, чтобы увидеть клиентов, даты создания и владельцев.')
            st.button('Обновить CRM и сделки',on_click=refresh_data,key='dashboard_refresh',disabled=refreshing or not can_refresh)
            return
        cache=st.session_state.get('dashboard_facts_cache')
        if cache is None or cache[0] is not clients or cache[1]!=today:
            cache=(clients,today,client_facts(clients,today))
            st.session_state.dashboard_facts_cache=cache
        try: tasks=store.tasks() if store is not None else pd.DataFrame()
        except StoreError:
            st.error('Не удалось прочитать ваши задачи. Повторите открытие Dashboard, чтобы корректно определить следующие контакты.')
            return
        facts=with_tasks(cache[2],tasks,today)
        if facts.empty:
            st.info('В снимке нет доступных контрагентов. Обновите CRM и сделки.')
            st.button('Обновить CRM и сделки',on_click=refresh_data,key='dashboard_refresh',disabled=refreshing or not can_refresh)
            return
        for key,default in [('dashboard_all_dates',True),('dashboard_from',today-timedelta(days=29)),('dashboard_to',today),('dashboard_sort',SORTS[0]),('dashboard_view','all')]:
            if key not in st.session_state: st.session_state[key]=default
        with st.container(key='dashboard-toolbar'):
            search,owner,project,options,action=st.columns([2.2,1.8,1.8,1,1.1],gap='small',vertical_alignment='bottom')
            with search: query=st.text_input('Поиск клиента',placeholder='Название контрагента…',key='dashboard_search')
            with owner: owners=_options('Владелец-сотрудник',facts,'owner_employee','dashboard_owners','Все менеджеры')
            with project: projects=_options('Проект',facts,'crm_project','dashboard_projects','Все проекты')
            with options:
                with st.popover('Условия',width='stretch'):
                    all_dates=st.checkbox('За всё время',key='dashboard_all_dates')
                    start=st.date_input('Добавлены с',key='dashboard_from',disabled=all_dates,format='DD.MM.YYYY')
                    end=st.date_input('Добавлены по',key='dashboard_to',disabled=all_dates,format='DD.MM.YYYY')
                    codes=_options('Код',facts,'code','dashboard_codes','Все коды, включая пустые')
                    archived=st.checkbox('Включая архивных',key='dashboard_archived')
                    sort=st.selectbox('Порядок строк',SORTS,key='dashboard_sort')
                    st.button('Сбросить фильтры',on_click=reset,args=(today,),key='dashboard_reset',width='stretch')
                    st.caption('Задачи и даты контактов относятся к вашей учётной записи. Фильтр менеджера показывает закрепление клиента в Моём Складе.')
            with action: st.button('↻ Обновить',on_click=refresh_data,key='dashboard_refresh',disabled=refreshing or not can_refresh,width='stretch',help='Обновить CRM, итоги заказов и покупок в фоне')
        if not all_dates and start>end:
            st.warning('Дата «Добавлены с» должна быть не позже даты «Добавлены по».');return
        base=facts if archived else facts[~facts.crm_archived.fillna(False).astype(bool)]
        base=select(base,None if all_dates else start,None if all_dates else end,owners,projects,codes,query)
        if global_query.strip(): base=select(base,query=global_query)
        counts={key:len(subset(base,key)) for key in VIEWS}
        with st.container(key='dashboard-views'):
            view_name=st.segmented_control('Рабочие списки',list(VIEWS),key='dashboard_view',format_func=lambda key:f'{VIEWS[key]} · {counts[key]}',label_visibility='collapsed',width='stretch') or 'all'
        remember()
        view=sort_clients(subset(base,view_name),sort)
        unknown=int((~facts.history_known|~facts.orders_known).sum())
        if unknown: st.caption(f'История {unknown} клиентов ещё не полная: «—» означает неизвестное значение. Нажмите «Обновить», чтобы уточнить сделки.')
        if refreshing: st.caption('CRM и сделки обновляются в фоне. Сейчас показан сохранённый список.')
        if not all_dates: st.caption(f'Добавлены с {start:%d.%m.%Y} по {end:%d.%m.%Y} включительно.')
        stamps=pd.to_numeric(facts.get('crm_activity_synced_at',facts.dashboard_synced_at),errors='coerce').dropna()
        updated=pd.Timestamp(stamps.max(),unit='s',tz='UTC').tz_convert('Europe/Moscow').strftime('%d.%m %H:%M') if len(stamps) else None
        st.markdown('<div class="dashboard-register"><b>'+safe(VIEWS[view_name]).upper()+'</b><span>Клиентов: '+str(len(view))+(' · CRM '+safe(updated)+' МСК' if updated else '')+' · Выберите строку для действий</span></div>',unsafe_allow_html=True)
        if view.empty:
            st.info('Контрагенты по выбранным условиям не найдены. Измените фильтры или рабочий список.');return
        size=int(st.session_state.get('dashboard_size',50))
        fingerprint=hashlib.sha256(repr((tuple(view.client_id),view_name,sort,size)).encode()).hexdigest()[:12]
        if st.session_state.get('dashboard_context')!=fingerprint:
            st.session_state.dashboard_context=fingerprint;st.session_state.dashboard_page=1
        pages=max(1,(len(view)+size-1)//size)
        page=min(int(st.session_state.get('dashboard_page',1)),pages)
        current=view.iloc[(page-1)*size:page*size]
        selected=st.session_state.get('dashboard_selected_id')
        if selected not in set(view.client_id): selected=None
        table_col,detail_col=st.columns([3.6,1.25],gap='small') if selected is not None else (st.container(),None)
        with table_col:
            names={'company':'Клиент','attention_status':'Внимание','created_at':'Добавлен','orders':'Заказы','purchases':'Покупки','turnover':'Покупки, ₽','last_purchase':'Покупал','next_contact':'Мой контакт','owner_employee':'Менеджер','crm_project':'Проект','code':'Код'}
            display=current[list(names)].rename(columns=names)
            colors={'Просрочен контакт':'#b42318','Связаться сегодня':'#a75708','Нет менеджера':'#a75708','Новый заказ':'#245fc1','Пора повторить заказ':'#a75708','Первый заказ':'#245fc1','Первый контакт':'#a75708','В работе':'#07815e','Есть покупки':'#07815e','Уточнить данные':'#667085'}
            styled=display.style.format(na_rep='—').map(lambda value:'color: '+colors.get(value,'#243554')+'; font-weight: 600',subset=['Внимание'])
            key=f'dashboard_grid_{fingerprint}_{page}_{st.session_state.get("dashboard_selection_version",0)}'
            def select_client(table=key,ids=tuple(int(v) for v in current.client_id)):
                rows=st.session_state.get(table,{}).get('selection',{}).get('rows',[])
                if rows and 0<=rows[0]<len(ids): st.session_state.dashboard_selected_id=ids[rows[0]]
                else: st.session_state.pop('dashboard_selected_id',None)
            pin={'pinned':True} if 'pinned' in inspect.signature(st.column_config.TextColumn).parameters else {}
            config={name:st.column_config.TextColumn(width=110) for name in display.columns}
            config.update({'Клиент':st.column_config.TextColumn(width=190,**pin),'Внимание':st.column_config.TextColumn(width=160,help='Выберите строку, чтобы прочитать причину и назначить контакт'),'Код':st.column_config.TextColumn(width=65),
                'Заказы':st.column_config.NumberColumn(width=65,format='%d',help='Все доступные заказы покупателей, во всех статусах. Заказ не подтверждает оплату или отгрузку.'),
                'Покупки':st.column_config.NumberColumn(width=72,format='%d',help='Количество проведённых отгрузок за всю доступную историю.'),
                'Покупки, ₽':st.column_config.NumberColumn(width=105,format='localized',help='Сумма проведённых отгрузок с НДС, без вычета возвратов. Не складывается с суммой заказов.')})
            for col in ['Добавлен','Покупал','Мой контакт']: config[col]=st.column_config.DatetimeColumn(width=86,format='DD.MM.YY')
            missing={'placeholder':'—'} if 'placeholder' in inspect.signature(st.dataframe).parameters else {}
            st.dataframe(styled,hide_index=True,width='stretch',height=min(610,36+26*len(current)),row_height=26,key=key,on_select=select_client,selection_mode='single-row',column_config=config,**missing)
        if detail_col is not None:
            with detail_col: detail(view[view.client_id==selected].iloc[0],today,store,on_client)
        a,b,c,d=st.columns([3,1,1,1],vertical_alignment='bottom')
        with a: st.caption(f'{(page-1)*size+1}–{min(page*size,len(view))} из {len(view)} · Колонки можно растягивать. Галочка слева открывает действия.')
        with b: st.selectbox('Строк',[25,50,100],index=1,key='dashboard_size')
        with c: st.number_input('Страница',min_value=1,max_value=pages,step=1,key='dashboard_page')
        with d:
            with st.popover('Как читать'):
                st.write('Заказы — документы заказов покупателей во всех статусах. Покупки — проведённые отгрузки. Эти количества не складываются: один заказ может отгружаться частями.')
                st.write('Покупки, ₽ — сумма всех доступных проведённых отгрузок с НДС, без возвратов. Список «Взять в работу» строится по заказам, покупкам и вашим задачам.')
                st.write('Задержка повторного заказа: прошло больше 1,5 обычного интервала. Интервал — медиана по минимум трём покупкам за 12 месяцев. Контакты и статус «В работе» учитывают только ваши задачи.')
                st.write('«Проект» берётся из дополнительного поля контрагента «Проект». Пустые поля показаны как «Не указан». Обновление идёт по кнопке или выбранному интервалу, пока приложение открыто.')
        remember()
