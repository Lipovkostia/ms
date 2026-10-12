"""Responsive client segments with editable rules and native click targets."""
from copy import deepcopy
import streamlit as st
from .client_segments import activity, select_block, DEFAULT_BLOCKS
from .presentation import money as rub


def render(clients,today,store,open_client,refresh_data):
    st.subheader('Клиенты по последней покупке')
    if 'crm_history_loaded' not in clients:
        st.info('Для блоков, владельцев и новых заказов нужно один раз обновить данные из Моего Склада.')
        st.button('Загрузить данные для блоков',on_click=refresh_data,key='crm_initial_refresh')
        return
    key='crm_block_rules:'+store.scope
    if key not in st.session_state:
        st.session_state[key]=store.get('preferences','client_blocks',deepcopy(DEFAULT_BLOCKS))
    blocks=st.session_state[key]
    search_col,refresh_col=st.columns([3,1])
    with search_col: query=st.text_input('Поиск контрагента',key='crm_search',placeholder='Введите название')
    with refresh_col: st.button('Обновить данные',on_click=refresh_data,key='crm_refresh',width='stretch')
    frame=activity(clients,today)
    managers=sorted(frame.owner_employee.unique())
    owner=st.multiselect('Владелец-сотрудник — закреплённый менеджер',managers,key='crm_managers',placeholder='Все менеджеры')
    if query: frame=frame[frame.company.str.contains(query,case=False,regex=False)]
    if owner: frame=frame[frame.owner_employee.isin(owner)]
    with st.expander('✏️ Настроить блоки'):
        st.caption('«С» включительно, «По» не включительно. Минимум покупок считается в заданном диапазоне дней. Пересекающиеся диапазоны могут включать одного клиента в несколько блоков.')
        with st.form('crm_rules_form'):
            number=st.number_input('Количество блоков',min_value=1,max_value=8,value=len(blocks),key='crm_blocks_number')
            st.caption('Чтобы добавить блок: измените количество и нажмите «Применить», затем настройте новую строку.')
            updated=[]
            for i,b in enumerate(blocks):
                st.markdown(f'**Блок {i+1}**')
                title=st.text_input('Название',value=b['name'],key=f'crm_name_{i}')
                a,z,m=st.columns(3)
                lo=a.number_input('С, дней',min_value=0,max_value=36500,value=int(b['start']),key=f'crm_start_{i}')
                hi=z.number_input('По, дней',min_value=1,max_value=36501,value=int(b['end']),key=f'crm_end_{i}')
                count=m.number_input('Минимум покупок',min_value=1,max_value=100000,value=int(b['minimum']),key=f'crm_min_{i}')
                updated.append(dict(name=title.strip(),start=int(lo),end=int(hi),minimum=int(count)))
            if st.form_submit_button('Применить настройки',width='stretch'):
                if any(not b['name'] or b['end']<=b['start'] for b in updated): st.error('Укажите название и значение «По» больше значения «С».')
                else:
                    updated=updated[:int(number)]
                    while len(updated)<number:
                        start=updated[-1]['end'] if updated else 0
                        updated.append(dict(name=f'Блок {len(updated)+1}',start=start,end=start+30,minimum=1))
                    store.put('preferences','client_blocks',updated)
                    st.session_state[key]=updated
                    st.rerun()
    st.caption('Покупка = проведённая отгрузка. Сумма — все доступные проведённые отгрузки, с НДС, без вычета возвратов. Сделки здесь считаются по числу отгрузок. Новый заказ — заказ покупателя, созданный за последние 10 дней; он не считается покупкой.')
    with st.container(key='crm-blocks'):
        columns=st.columns(2,gap='medium')
        for index,block in enumerate(blocks):
            view=select_block(frame,block,today)
            with columns[index%2],st.container(border=True):
                st.markdown(f"### {block['name']}")
                st.caption(f"{block['start']}–{block['end']} дней · минимум {block['minimum']} покупок")
                st.metric('Клиентов',len(view))
                st.metric('Общая сумма покупок',rub(view.total_amount.sum()))
                with st.expander('Показать клиентов',expanded=False):
                    if view.empty: st.info('В этом блоке нет клиентов по выбранным условиям.')
                    else:
                        page_key=f'crm_page_{index}'
                        if st.session_state.get(page_key,1)>max(1,(len(view)+9)//10): st.session_state[page_key]=1
                        page=st.number_input('Страница',min_value=1,max_value=max(1,(len(view)+9)//10),key=f'crm_page_{index}')
                        for row in view.iloc[(page-1)*10:page*10].itertuples():
                            st.button(row.company+' →',key=f'crm_client_{index}_{row.client_id}',on_click=open_client,args=(row.client_id,),width='stretch')
                            st.caption(f"{rub(row.total_amount)} · сделок: {row.purchase_count} · в диапазоне: {row.window_purchases}\n\nПоследняя покупка: {row.last_purchase:%d.%m.%Y} · {int(row.days_since)} дн. назад\n\nМенеджер: {row.owner_employee}")
                            if row.recent_orders: st.success(f'Новый заказ в базе · за 10 дней: {row.recent_orders}',icon='🟢')
                            st.divider()
    st.caption(f'Без покупок в доступной истории: {int(frame.last_purchase.isna().sum())}. Такие клиенты не попадают в блоки давности.')
