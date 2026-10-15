"""Compact CRM inbox. Native grid provides drag-to-resize column headers."""
from datetime import timedelta
import hashlib
import pandas as pd
import streamlit as st
from .dashboard_data import FIELDS,listing,select
from .presentation import safe

SORTS=['Сначала новые','Сначала старые']


def reset(today):
    st.session_state.update(dashboard_from=today-timedelta(days=30),dashboard_to=today,
        dashboard_all_dates=False,dashboard_owners=[],dashboard_projects=[],dashboard_codes=[],
        dashboard_search='',dashboard_sort=SORTS[0],dashboard_page=1,dashboard_archived=False,
        global_search='')


def _options(label,frame,field,key,placeholder):
    values=sorted(frame[field].unique().tolist(),key=str.casefold)
    # A successful refresh can remove an old employee/project/code option.
    if key in st.session_state:
        st.session_state[key]=[v for v in st.session_state[key] if v in values]
    return st.multiselect(label,values,key=key,placeholder=placeholder)


def render(clients,today,on_client,refresh_data,refreshing=False,can_refresh=False,global_query=''):
    with st.container(border=True,key='dashboard-inbox'):
        st.subheader('Недавно добавленные контрагенты')
        st.caption('Дата добавления в CRM · код · закреплённый сотрудник · проект')
        loaded=set(FIELDS).issubset(clients.columns)
        search,filters,action=st.columns([2.5,1,1],vertical_alignment='bottom')
        with search:
            query=st.text_input('Поиск по названию',placeholder='Название контрагента…',key='dashboard_search')
        active=sum(bool(st.session_state.get('dashboard_'+name)) for name in ['owners','projects','codes','all_dates','archived'])
        with filters:
            with st.popover('Фильтры',width='stretch',disabled=not loaded):
                st.markdown('**Фильтры контрагентов**')
                all_dates=st.checkbox('За всё время',key='dashboard_all_dates')
                archived=st.checkbox('Включая архивных',key='dashboard_archived')
                if loaded:
                    frame=listing(clients,archived)
                    owners=_options('Владелец-сотрудник',frame,'owner_employee','dashboard_owners','Все сотрудники')
                    projects=_options('Проект',frame,'crm_project','dashboard_projects','Все проекты')
                    codes=_options('Код',frame,'code','dashboard_codes','Все коды, включая пустые')
        with action:
            st.button('↻ Обновить список',on_click=refresh_data,key='dashboard_refresh',
                disabled=refreshing or not can_refresh,width='stretch',help='Загрузить только контрагентов и сотрудников, без истории продаж')
        if refreshing: st.caption('Обновление выполняется в фоне. Пока доступен сохранённый список.')
        if not can_refresh: st.caption('Для обновления восстановите подключение к Моему Складу в верхней панели.')
        error=st.session_state.get('live_error')
        if error: st.error(error)
        if not loaded:
            st.info('В сохранённой базе ещё нет дат создания и дополнительных полей CRM. Нажмите «Обновить список» — история продаж повторно не загружается.')
            return

        a,b,c,d=st.columns([1,1,1.25,1],vertical_alignment='bottom')
        with a: start=st.date_input('Добавлены с',value=today-timedelta(days=30),key='dashboard_from',disabled=all_dates,format='DD.MM.YYYY')
        with b: end=st.date_input('Добавлены по',value=today,key='dashboard_to',disabled=all_dates,format='DD.MM.YYYY')
        with c: sort=st.selectbox('По дате добавления',SORTS,key='dashboard_sort')
        with d: st.button('Сбросить фильтры',on_click=reset,args=(today,),key='dashboard_reset',width='stretch')
        if all_dates: st.caption('Показаны контрагенты за всё время; ограничение по датам отключено.')
        if not all_dates and start>end:
            st.warning('Дата «Добавлены с» должна быть не позже даты «Добавлены по».')
            return
        view=select(frame,None if all_dates else start,None if all_dates else end,owners,projects,codes,query,sort==SORTS[1])
        if global_query.strip():
            view=select(view,query=global_query,oldest_first=sort==SORTS[1])
            st.caption('Также применяется поиск из верхней панели: '+global_query)
        missing=int(frame.created_at.isna().sum())
        if missing: st.caption(f'У {missing} контрагентов дата создания не получена из API. Они видны при выборе «За всё время».')
        if not frame.crm_project_field_present.any():
            st.caption('Дополнительное поле «Проект» в полученных карточках не найдено. Проекты из заказов контрагентам не присваиваются.')
        stamps=pd.to_numeric(frame.dashboard_synced_at,errors='coerce').dropna()
        updated=pd.Timestamp(stamps.max(),unit='s',tz='UTC').tz_convert('Europe/Moscow').strftime('%d.%m.%Y %H:%M') if len(stamps) else None
        st.markdown('<div class="dashboard-register"><b>КОНТРАГЕНТЫ</b><span>'+str(len(view))+' из '+str(len(frame))+(f' · Фильтров: {active}' if active else '')+(' · Список обновлён '+safe(updated)+' МСК' if updated else '')+'</span></div>',unsafe_allow_html=True)
        if view.empty:
            st.info('Контрагенты по выбранным условиям не найдены. Измените даты или сбросьте фильтры.')
            return
        if 'dashboard_size' not in st.session_state: st.session_state.dashboard_size=50
        size=int(st.session_state.dashboard_size)
        context=(str(start),str(end),all_dates,archived,tuple(owners),tuple(projects),tuple(codes),query,global_query,sort,size)
        fingerprint=hashlib.sha256(repr((context,tuple(view.client_id))).encode()).hexdigest()[:14]
        if st.session_state.get('dashboard_context')!=fingerprint:
            st.session_state.dashboard_context=fingerprint
            st.session_state.dashboard_page=1
        pages=max(1,(len(view)+size-1)//size)
        page=min(int(st.session_state.get('dashboard_page',1)),pages)
        current=view.iloc[(page-1)*size:page*size]
        columns={'company':'Контрагент','created_at':'Дата добавления','code':'Код','owner_employee':'Владелец-сотрудник','crm_project':'Проект'}
        display=current[list(columns)].rename(columns=columns)
        key='dashboard_grid_'+fingerprint+'_'+str(page)
        def open_selection(table=key,ids=tuple(int(v) for v in current.client_id)):
            rows=st.session_state.get(table,{}).get('selection',{}).get('rows',[])
            if rows and 0<=rows[0]<len(ids): on_client(ids[rows[0]])
        st.dataframe(display,hide_index=True,width='stretch',height=min(590,35+28*len(current)),
            row_height=28,key=key,selection_mode='single-row',on_select=open_selection,
            column_config={
                'Контрагент':st.column_config.TextColumn(width=310),
                'Дата добавления':st.column_config.DatetimeColumn(format='DD.MM.YYYY HH:mm',width=165),
                'Код':st.column_config.TextColumn(width=100),
                'Владелец-сотрудник':st.column_config.TextColumn(width=195),
                'Проект':st.column_config.TextColumn(width=180)})
        st.caption('Перетаскивайте границы заголовков, чтобы менять ширину колонок. Отметьте строку слева, чтобы открыть карточку клиента. На телефоне таблица прокручивается по горизонтали.')
        a,b,c=st.columns([2,1,1],vertical_alignment='bottom')
        with a: st.caption(f'Показаны {(page-1)*size+1}–{min(page*size,len(view))} из {len(view)}')
        with b: st.selectbox('Строк на странице',[25,50,100],key='dashboard_size')
        with c: st.number_input('Страница',min_value=1,max_value=pages,step=1,key='dashboard_page')
