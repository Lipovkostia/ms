from datetime import timedelta
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
from sales_center.analytics import metrics, orders, client_summary, period, monthly, companions
from sales_center.recommendations import generate, message
from sales_center.storage import Store, StoreError
from sales_center.moysklad import MoySkladError
from sales_center.sync import refresh, due, restore
from sales_center.connection_config import read_config
from sales_center.snapshots import SnapshotCache, SnapshotError, source_id
from sales_center.identity import identity
from sales_center.theme import CSS
from sales_center.presentation import safe, pill, stat, client_row, purchase_chart, category_chart
from sales_center.settings import connections, model_picker

st.set_page_config(page_title='AI Sales Center', page_icon='📈', layout='wide')
st.markdown(CSS,unsafe_allow_html=True)
TODAY=pd.Timestamp.now(tz='Europe/Moscow').date()
user_id,user_name=identity()
if st.session_state.get('_active_user',user_id)!=user_id:
    for key in list(st.session_state): del st.session_state[key]
st.session_state['_active_user']=user_id
try:
    secret_settings={key:st.secrets.get(key) for key in ['MOYSKLAD_TOKEN','DATABASE_URL','MOYSKLAD_PRIVATE_DEPLOYMENT','MOYSKLAD_AUTO_CONNECT','MOYSKLAD_SYNC_MINUTES']}
except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError): secret_settings={}
config=read_config(secret_settings,user_id)
SNAPSHOT_PATH=Path(__file__).parent/'.runtime'/'moysklad.db'

def cache_for(token):
    try:
        return SnapshotCache(SNAPSHOT_PATH,token,user_id,database_url=config.database_url)
    except (StoreError,OSError,ValueError):
        st.session_state.sync_cache_error='Хранилище снимков недоступно. Проверьте настройки базы. Ключ остаётся в защищённых настройках.'
        return None

# Removing access or a configured key must also clear a previously managed session.
if st.session_state.get('sync_origin')=='managed' and not (config.token and config.authorized):
    for key in list(st.session_state):
        if key.startswith(('live_','sync_','client_','draft_','workspace_')): del st.session_state[key]

# Managed credentials survive application deployment in Streamlit Secrets.
if config.automatic and not st.session_state.get('sync_disconnected'):
    managed=source_id(config.token)
    previous=st.session_state.get('sync_managed_source')
    if previous!=managed:
        for key in ['live_data','live_analytics','sync_success_at','sync_attempt_at','sync_bootstrap_done']:
            st.session_state.pop(key,None)
        st.session_state.sync_managed_source=managed
        st.session_state.sync_token=config.token
        st.session_state.sync_origin='managed'
    if 'sync_interval' not in st.session_state: st.session_state.sync_interval=config.interval
    if not st.session_state.get('sync_bootstrap_done'):
        st.session_state.sync_bootstrap_done=True
        cache=cache_for(config.token)
        restored=False
        if cache is not None:
            try: restored=restore(st.session_state,TODAY,cache)
            except (StoreError,SnapshotError): st.session_state.sync_cache_error='Сохранённый снимок недоступен. Выполняется новая загрузка.'
        if not restored and 'live_data' not in st.session_state:
            try:
                with st.status('Автоподключение к Моему Складу · сохранённый токен',expanded=True) as status:
                    def bootstrap_report(stage,count,total): status.update(label=f'{stage}: {count:,} / {total:,}' if total else stage)
                    refresh(st.session_state,TODAY,token=config.token,progress=bootstrap_report,retain=True,cache=cache)
                    status.update(label='Подключение восстановлено',state='complete',expanded=False)
            except MoySkladError as exc: st.session_state.live_error=str(exc)
            except (KeyError,TypeError,ValueError): st.session_state.live_error='Не удалось обработать данные. Повторите обновление; сохранённый токен вводить заново не нужно.'

if 'page' not in st.session_state: st.session_state.page='Клиенты'
PAGES=['Главная','Клиенты','Карточка клиента','Возврат клиентов','Товарная аналитика','AI-рекомендации','Задачи','Эффективность','Сообщения','Настройки']
with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-mark"></div><div><div class="brand-title">AI-Помощник</div><div class="brand-sub">для оптовых продаж</div></div></div>',unsafe_allow_html=True)
    nav_icons=['⌂','♧','▣','↻','▥','✦','☑','↗','▤','⚙']
    page=st.radio('Раздел',PAGES,key='page',format_func=lambda name:nav_icons[PAGES.index(name)]+'  '+name)
    st.divider()
    st.markdown('<div class="nav-foot"><b>✦ Аналитика продаж</b><br>История покупок помогает выбрать следующий контакт.</div>',unsafe_allow_html=True)
    st.caption(user_name)
    if user_id=='personal': st.caption('Персональный режим · вход сотрудников настраивается в Настройках.')
    else:
        if st.button('Выйти'): st.logout()

@st.fragment(run_every='60s')
def sync_panel():
    interval=st.session_state.get('sync_interval',0)
    auto=due(st.session_state,interval)
    with st.popover('↻ Синхронизировать с Мой Склад' if 'live_data' in st.session_state else '↻ Подключить Мой Склад',width='stretch'):
        if config.token:
            if config.authorized:
                st.success('Постоянный токен настроен. После обновления сайта он берётся из Streamlit Secrets.')
                if st.session_state.get('sync_disconnected') and st.button('Восстановить постоянное подключение'):
                    st.session_state.pop('sync_disconnected',None)
                    st.session_state.pop('sync_bootstrap_done',None)
                    st.rerun()
            else:
                st.warning('Токен сохранён, но автоматический доступ закрыт. Настройте вход сотрудников либо закрытый доступ Streamlit Cloud и MOYSKLAD_PRIVATE_DEPLOYMENT=true.')
        else:
            st.caption('Чтобы не вводить ключ после обновления, один раз добавьте MOYSKLAD_TOKEN в Manage app → Settings → Secrets. Инструкция — в Настройках.')
        with st.form('moysklad_connect',clear_on_submit=True):
            token=st.text_input('API-токен Моего Склада',type='password',help='При постоянном подключении оставьте поле пустым. Новый ввод временно переключает источник этой сессии.')
            retain=st.checkbox('Держать введённый токен в памяти этой сессии для обновления',value=True)
            requested=st.form_submit_button('Загрузить / обновить данные')
        quick=st.button('Обновить сейчас',type='primary',disabled=not st.session_state.get('sync_token'))
        interval=st.selectbox('Период обновления (минут)',[0,15,30,60],format_func=lambda n:'Только вручную' if n==0 else f'Каждые {n} минут',key='sync_interval')
        st.caption('При открытии сначала восстанавливается сохранённый снимок. Обновление из Моего Склада работает при открытой вкладке; таймер проверяется раз в минуту. Первичная загрузка при отсутствии снимка может занять несколько минут. Это не поток в реальном времени.')
        if interval and not st.session_state.get('sync_token') and not (requested and retain): st.info('Для автообновления загрузите данные с флажком хранения токена в сессии.')
        if requested or quick or auto:
            try:
                selected_token=(token.strip() if requested else '') or st.session_state.get('sync_token') or (config.token if config.authorized else '')
                if not selected_token: raise MoySkladError('Введите токен или настройте постоянное подключение в Streamlit Secrets.')
                cache=cache_for(selected_token)
                # A repeated connect with the same key can restore an existing snapshot.
                if requested and token.strip() and 'live_data' not in st.session_state and cache is not None:
                    try:
                        if restore(st.session_state,pd.Timestamp.now(tz='Europe/Moscow').date(),cache):
                            if retain: st.session_state.sync_token=selected_token
                            st.session_state.sync_disconnected=False
                            st.session_state.sync_origin='managed' if selected_token==config.token else 'manual'
                            st.rerun()
                    except (StoreError,SnapshotError): pass
                with st.status('Подключение…',expanded=True) as status:
                    def report(stage,count,total): status.update(label=f'{stage}: {count:,} / {total:,}' if total else stage)
                    fresh=refresh(st.session_state,pd.Timestamp.now(tz='Europe/Moscow').date(),token=selected_token,progress=report,retain=retain if requested and token.strip() else True,cache=cache)
                    st.session_state.sync_disconnected=False
                    st.session_state.sync_origin='managed' if selected_token==config.token else 'manual'
                    status.update(label='Данные проверены и загружены',state='complete',expanded=False)
                st.success(f'Подключение выполнено: {len(fresh[0]):,} клиентов, {fresh[2].order_id.nunique():,} отгрузок.')
                st.rerun()
            except MoySkladError as exc: st.session_state.live_error=str(exc)
            except (KeyError,TypeError,ValueError) as exc: st.session_state.live_error=f'Ошибка обработки данных ({type(exc).__name__}). Прежние данные сохранены. Сообщите этот код администратору.'
        if st.session_state.get('live_error'): st.error(st.session_state.live_error)
        if st.session_state.get('sync_cache_error'): st.warning(st.session_state.sync_cache_error)
        if st.session_state.get('sync_restored'): st.caption('Открыт сохранённый снимок. Его дата показана ниже; новые изменения появятся после следующего обновления.')
        if st.session_state.get('sync_success_at'):
            stamp=pd.Timestamp(st.session_state.sync_success_at,unit='s',tz='UTC').tz_convert('Europe/Moscow')
            st.caption(f'Успешное обновление: {stamp:%d.%m.%Y %H:%M} МСК')
        if st.button('Отключить источник в этой сессии'):
            for key in list(st.session_state):
                if key.startswith(('live_','sync_','provider_','client_draft_','draft_')): del st.session_state[key]
            st.session_state.sync_disconnected=True
            st.rerun()
with st.container(key='topbar'):
    search_col,sync_col,status_col,user_col=st.columns([2.8,2,1.8,1.3],gap='small',vertical_alignment='center')
    with search_col:
        global_search=st.text_input('Поиск по клиентам, товарам, контактам',placeholder='⌕  Поиск по клиентам, товарам, контактам…',key='global_search')
    with sync_col: sync_panel()
    with status_col:
        if st.session_state.get('sync_success_at'):
            updated=pd.Timestamp(st.session_state.sync_success_at,unit='s',tz='UTC').tz_convert('Europe/Moscow')
            st.markdown(f'<div class="top-status"><span class="status-dot"></span>Данные обновлены {updated:%d.%m.%Y %H:%M}<br>{'Сохранённый снимок' if st.session_state.get('sync_restored') else 'Мой Склад'} · МСК</div>',unsafe_allow_html=True)
        else: st.markdown('<div class="top-status"><span class="status-dot off"></span>Источник не подключён</div>',unsafe_allow_html=True)
    with user_col:
        display_name=user_name if user_id!='personal' else 'Мой кабинет'
        initial=display_name[:1].upper()
        st.markdown(f'<div class="user-profile"><div class="avatar">{safe(initial)}</div><div>{safe(display_name)}<span>Менеджер продаж</span></div></div>',unsafe_allow_html=True)
with st.container(key='workspace-title' if page in ['Клиенты','Карточка клиента'] else 'page-title'):
    st.title(page)
source='Мой Склад'
if page=='Настройки':
    connections()
    st.stop()
if 'live_data' not in st.session_state:
    st.markdown('<div class="empty-hero"><span class="pill">Ваш центр управления продажами</span><h2>Клиенты, аналитика и следующий шаг —<br>в одном рабочем пространстве</h2><p>Подключите Мой Склад, чтобы увидеть свою клиентскую базу, историю покупок и возможности для следующего контакта.</p><p>Нажмите «Подключить Мой Склад» в верхней панели и вставьте токен. Первичная загрузка годовой истории может занять несколько минут.</p></div>',unsafe_allow_html=True)
    st.info('Подключите Мой Склад в панели выше. Здесь отображаются только реальные данные вашего аккаунта. Настройки мессенджеров и AI доступны до загрузки.')
    st.stop()
clients,products,lines=st.session_state.live_data
if clients.empty:
    st.info('В аккаунте нет доступных контрагентов. Проверьте права доступа.')
    st.stop()
account=clients.attrs.get('account_id')
if not account:
    st.error('API не вернул accountId. Записи не сохраняются, чтобы не смешивать разные аккаунты. Обновите подключение.')
    st.stop()
try:
    database_url=config.database_url
    store=Store(Path(__file__).parent/'.runtime'/'moysklad.db',scope=f'{account}:{user_id}',database_url=database_url)
except StoreError as exc:
    st.error(str(exc))
    st.stop()
except (OSError,ValueError):
    st.error('База записей недоступна. Проверьте DATABASE_URL или права записи в .runtime. Секрет подключения не выводится.')
    st.stop()
if 'live_analytics' not in st.session_state:
    st.session_state.live_analytics=(client_summary(clients,lines,TODAY),generate(client_summary(clients,lines,TODAY),lines,products,TODAY))
summary,recommendations=st.session_state.live_analytics
with st.sidebar:
    with st.expander('Источник и хранение'):
        st.caption('Реальные проведённые отгрузки за 12 месяцев · RUB. Оборот без НДС и без вычета возвратов.')
        st.caption(f'Исключено внутренних отгрузок: {lines.attrs.get("excluded_internal_shipments",0)} · пустых документов: {lines.attrs.get("excluded_empty_shipments",0)}')
        if not store.persistent: st.caption('SQLite: облако может удалить записи при перезапуске. Для постоянного хранения настройте PostgreSQL.')
        if lines.cost.isna().any(): st.caption('Себестоимость части позиций недоступна: прибыль таких периодов не рассчитывается.')
with st.sidebar:
    with st.expander('Период аналитики'):
        start=st.date_input('Начало периода',TODAY-timedelta(days=90),key='period_start')
        end=st.date_input('Конец периода',TODAY,key='period_end')
        st.caption('Период влияет на суммы и графики. Циклы рассчитаны по 12 месяцам.')
if start>end: st.error('Начало периода не может быть позже конца.'); st.stop()
selected=period(lines,start,end)

def save_record(kind,key,value):
    try:
        store.put(kind,key,value)
        st.success('Запись сохранена.')
    except StoreError:
        st.error('Не удалось сохранить запись. Проверьте доступность базы и повторите попытку.')

def rub(value):
    return f'{value:,.0f} ₽'.replace(',', ' ') if pd.notna(value) else 'Нет данных'

def open_client(cid):
    st.session_state.client_id = int(cid)
    st.session_state.workspace_client = int(cid)
    st.session_state.page = 'Карточка клиента'

def client_picker(key):
    ids = clients.client_id.tolist()
    initial = st.session_state.get('client_id', ids[0])
    return st.selectbox('Клиент', ids, index=ids.index(initial) if initial in ids else 0,
                        format_func=lambda cid: clients.set_index('client_id').loc[cid,'company'], key=key)

def kpis(frame):
    m = metrics(frame)
    cols = st.columns(4)
    for col, label, value in zip(cols, ['Оборот', 'Заказы', 'Средний чек', 'Валовая прибыль'],
                                  [rub(m['revenue']), str(m['orders']), rub(m['average']), rub(m['profit'])]):
        col.metric(label, value)
    margin = f'{m["margin"]:.1f}%' if pd.notna(m['margin']) else 'нет данных'
    st.caption(f'Маржинальность: {margin} · Количество: {m["quantity"]:,.0f} (сумма в единицах каждого товара). Показатели за выбранный период.')

def graph(frame):
    if frame.empty:
        st.info('В выбранном периоде нет заказов.')
        return
    f = monthly(frame).rename(columns={'month':'Месяц','revenue':'Оборот','profit':'Валовая прибыль'})
    st.plotly_chart(px.line(f, x='Месяц', y=['Оборот','Валовая прибыль'], markers=True,
                            color_discrete_sequence=['#14946B','#255786'], labels={'value':'Рубли','variable':'Показатель'}), width='stretch')

def task_form(cid, key, action='Связаться с клиентом', rec_id=None):
    with st.form(f'task_{key}'):
        title = st.text_input('Задача', value=action, key=f'title_{key}')
        due = st.date_input('Дата следующего контакта', TODAY, key=f'due_{key}')
        note = st.text_area('Заметка', key=f'note_{key}')
        if st.form_submit_button('Создать задачу'):
            try:
                store.add(cid,title,due,note,rec_id)
                st.success('Задача сохранена. Она доступна в разделе «Задачи».')
            except (ValueError,StoreError) as exc:
                st.error(str(exc) if isinstance(exc,ValueError) else 'Не удалось сохранить задачу.')

def recommendation_cards(frame, limit=15):
    if frame.empty:
        st.info('Нет рекомендаций для выбранных условий.')
        return
    processed = set(store.processed().recommendation_id)
    for r in frame.head(limit).itertuples():
        with st.expander(f'{"🟠" if r.priority == "Высокий" else "🟢"} {r.company} · {r.title}'):
            st.write(r.reason)
            st.write('**Рекомендуемое действие:**', r.action)
            st.caption(f'Приоритет: {r.priority} · Возможный дополнительный оборот: {rub(r.effect)} (оценка, не гарантированный результат).')
            st.caption('Оценка: возврат — исторический средний чек; сопутствующие товары — цена × 6 единиц; снижение — разница первого и третьего месяцев; рост — 15% среднего чека. Наличие и актуальные цены не подтверждены.')
            st.button('Открыть карточку', key=f'open_{r.id}', on_click=open_client, args=(r.client_id,))
            draft = st.text_area('Черновик сообщения — можно редактировать', store.get('draft',r.id,message(r.company,r.action)), key=f'draft_{r.id}')
            if st.button('Сохранить черновик',key=f'save_{r.id}'):
                save_record('draft',r.id,draft)
            st.code(draft, language=None)
            st.caption('Используйте кнопку копирования справа в блоке текста. Сообщения не отправляются.')
            st.download_button('Скачать черновик', draft, file_name='message.txt', key=f'dl_{r.id}')
            task_form(r.client_id,r.id,r.action,r.id)
            if r.id in processed:
                st.success('Рекомендация обработана менеджером')
            elif st.button('Отметить обработанной', key=f'process_{r.id}'):
                try:
                    store.process(r.id)
                    st.rerun()
                except StoreError: st.error('Не удалось сохранить обработку рекомендации.')


if page == 'Главная':
    kpis(selected)
    left,right = st.columns([1.5,1])
    with left:
        st.subheader('Динамика продаж')
        graph(selected)
    with right:
        st.subheader('Контакты на сегодня и просроченные')
        t = store.tasks()
        t = t[(t.due <= str(TODAY)) & (~t.status.isin(['Выполнена','Отменена']))]
        if t.empty:
            st.info('Задач пока нет. Создайте контакт из карточки клиента или рекомендации.')
        else:
            t = t.merge(clients[['client_id','company']],on='client_id')
            st.dataframe(t[['company','title','due','status']].rename(columns={'company':'Клиент','title':'Задача','due':'Срок','status':'Статус'}), hide_index=True,width='stretch')
    st.subheader('Лучшие возможности')
    st.caption('Рекомендации учитывают всю доступную историю, независимо от выбранного периода графиков.')
    recommendation_cards(recommendations.sort_values('effect',ascending=False),5)
elif page in ['Клиенты','Карточка клиента']:
    active_count=int((summary.order_count>0).sum())
    delayed_count=int((summary.cycle_ratio>1.5).sum())
    potential=recommendations.groupby('client_id').effect.max().sum() if len(recommendations) else 0
    tasks=store.tasks()
    planned=int((~tasks.status.isin(['Выполнена','Отменена'])).sum())
    cards=[('Всего клиентов',str(len(clients)),'Контрагенты Моего Склада','♧','blue'),
           ('С покупками',str(active_count),'За последние 12 месяцев','♧','mint'),
           ('Заказ задерживается',str(delayed_count),'По индивидуальному циклу','◷','orange'),
           ('Потенциал продаж',rub(potential),'Оценка по рекомендациям','↗','mint'),
           ('Контакты в плане',str(planned),'Ваши открытые задачи','☑','purple')]
    with st.container(key='kpi-rack'):
        for col,card in zip(st.columns(5,gap='small'),cards):
            with col: st.markdown(stat(*card),unsafe_allow_html=True)
    with st.container(key='workspace'):
        left,center,right=st.columns([1.02,1.65,1.35],gap='medium')
        with left,st.container(border=True,key='client-list'):
            st.subheader('Приоритетные клиенты')
            search=st.text_input('Поиск по названию компании или городу',placeholder='Название компании или город',label_visibility='collapsed')
            priorities=st.multiselect('Приоритет',['Высокий','Средний','Низкий'],placeholder='Все приоритеты',label_visibility='collapsed')
            view=summary[summary.company.str.contains(search,case=False,regex=False)|summary.city.str.contains(search,case=False,regex=False)]
            if global_search:
                matching=clients.company.str.contains(global_search,case=False,regex=False)|clients.city.str.contains(global_search,case=False,regex=False)
                for field in ['phone','email']:
                    if field in clients: matching=matching|clients[field].fillna('').str.contains(global_search,case=False,regex=False)
                matching_ids=set(clients.loc[matching,'client_id'])
                matching_ids.update(lines.loc[lines['product'].str.contains(global_search,case=False,regex=False),'client_id'])
                view=view[view.client_id.isin(matching_ids)]
            if priorities: view=view[view.priority.isin(priorities)]
            view=view.assign(rank=view.priority.map({'Высокий':0,'Средний':1,'Низкий':2})).sort_values(['rank','revenue'],ascending=[True,False])
            if view.empty: st.info('Клиенты не найдены. Измените поиск или фильтры.'); st.stop()
            ids=view.client_id.tolist()
            if st.session_state.get('workspace_client') not in ids: st.session_state.workspace_client=ids[0]
            cid=st.session_state.workspace_client
            st.caption(f'Найдено {len(view):,} · Оборот за 12 месяцев')
            if st.session_state.get('client_list_page',1)>max(1,(len(view)+5)//6): st.session_state.client_list_page=1
            offset=st.session_state.get('client_list_page',1)
            for item in view.iloc[(offset-1)*6:offset*6].itertuples():
                with st.container(key=f'client-item-{item.client_id}'):
                    st.markdown(client_row(item,item.client_id==cid),unsafe_allow_html=True)
                    st.button('Открыть карточку — '+item.company,key=f'pick_{item.client_id}',on_click=lambda value: st.session_state.update(workspace_client=value),args=(item.client_id,),width='stretch')
            st.number_input('Страница клиентов',min_value=1,max_value=max(1,(len(view)+5)//6),value=1,key='client_list_page')
            with st.expander('Все клиенты · таблица'):
                st.selectbox('Выберите клиента',ids,format_func=lambda x:clients.set_index('client_id').loc[x,'company'],key='workspace_client')
                st.dataframe(view[['company','city','revenue','last_order','priority']].rename(columns={'company':'Клиент','city':'Город','revenue':'Оборот, ₽','last_order':'Последняя покупка','priority':'Приоритет'}),hide_index=True,width='stretch')
        c=summary.set_index('client_id').loc[cid]
        contact=clients.set_index('client_id').loc[cid]
        own=period(lines[lines.client_id==cid],start,end)
        with center,st.container(border=True,key='client-detail'):
            st.caption('ОБЗОР КЛИЕНТА')
            st.markdown(f'<div class="workspace-heading"><h2>{safe(c.company)}</h2>{pill(c.priority+" приоритет","mint" if c.priority=="Высокий" else "blue")}</div>',unsafe_allow_html=True)
            badges=pill('Повторные покупки' if c.order_count>1 else 'Одна покупка' if c.order_count==1 else 'Пока без покупок')
            if c.segment!='Не указан': badges+=' '+pill(c.segment,'purple')
            st.markdown(badges,unsafe_allow_html=True)
            phone=contact.get('phone') or 'Телефон не указан'
            email=contact.get('email') or 'Email не указан'
            st.markdown(f'<div class="contact-line">♧ &nbsp;{safe(phone)} &nbsp; · &nbsp; ✉ {safe(email)}<br>⌖ &nbsp;{safe(c.city)}</div>',unsafe_allow_html=True)
            tabs=st.tabs(['Обзор','История заказов','Товары','Заметки','Контакты'])
            with tabs[0]:
                m=metrics(own)
                a,b,d=st.columns(3,gap='small')
                a.metric('Оборот за период',rub(m['revenue']))
                b.metric('Средний чек',rub(m['average']))
                d.metric('Частота заказов',f'{c.frequency:.1f} / 30 дн.')
                chart_left,chart_right=st.columns([1.15,1],gap='small')
                with chart_left,st.container(border=True):
                    st.markdown('**Динамика покупок**')
                    if own.empty: st.info('Нет заказов за период.')
                    else: st.plotly_chart(purchase_chart(own),width='stretch',config={'displayModeBar':False})
                with chart_right,st.container(border=True):
                    st.markdown('**Популярные категории**')
                    if own.empty: st.caption('Нет покупок за период.')
                    else: st.plotly_chart(category_chart(own),width='stretch',config={'displayModeBar':False})
                st.markdown('**Последние заказы**')
                history=orders(own).sort_values('date',ascending=False).head(5)
                if history.empty: st.caption('За выбранный период отгрузок нет.')
                else:
                    names=own.groupby('order_id')['product'].agg(lambda values:', '.join(dict.fromkeys(values)))
                    recent=history[['date','revenue']].copy()
                    recent['products']=history.order_id.map(names)
                    recent['status']='Проведена'
                    recent['date']=recent.date.dt.strftime('%d.%m.%Y')
                    st.dataframe(recent.rename(columns={'date':'Дата','revenue':'Сумма, ₽','products':'Товары','status':'Отгрузка'}),hide_index=True,width='stretch',height=225)
                with st.expander('Цикл заказов и формулы'):
                    st.write('Обычный цикл (медиана): '+(f'{c.cycle:.0f} дней' if pd.notna(c.cycle) else 'недостаточно истории'))
                    st.caption('Цикл определяется при ≥3 заказах; частота = число заказов × 30 / дней с первого заказа до сегодня.')
            with tabs[1]: st.dataframe(orders(own).sort_values('date',ascending=False).drop(columns='client_id').rename(columns={'order_id':'Отгрузка','date':'Дата','revenue':'Оборот, ₽','cost':'Себестоимость, ₽','profit':'Валовая прибыль, ₽'}),hide_index=True,width='stretch')
            with tabs[2]: st.dataframe(own.groupby('product',as_index=False).agg(quantity=('quantity','sum'),revenue=('revenue','sum'),orders=('order_id','nunique')).rename(columns={'product':'Товар','quantity':'Количество','revenue':'Оборот, ₽','orders':'Заказов'}),hide_index=True,width='stretch')
            with tabs[3]:
                note=st.text_area('Заметка о клиенте',store.get('note',cid,''),key=f'client_note_{cid}')
                if st.button('Сохранить заметку'): save_record('note',cid,note)
            with tabs[4]:
                st.write('Телефон: '+str(contact.get('phone') or 'не указан'))
                st.write('Email: '+str(contact.get('email') or 'не указан'))
                st.write('Адрес: '+c.city)
        with right,st.container(border=True,key='draft-panel'):
            st.subheader('✦ AI-рекомендации')
            own_recs=recommendations[recommendations.client_id==cid]
            if own_recs.empty:
                st.markdown('<div class="ai-box"><b>Обсудите следующий заказ</b>В истории клиента пока нет достаточных сигналов для персональной рекомендации.</div>',unsafe_allow_html=True)
            else:
                reasons=''.join('<li>'+safe(r.reason)+'</li>' for r in own_recs.head(3).itertuples())
                effect=own_recs.effect.max()
                st.markdown(f'<div class="ai-box"><b>✦ Почему стоит связаться?</b><ul>{reasons}</ul><div class="estimate">Возможный дополнительный оборот: {safe(rub(effect))} · оценка, не гарантия</div></div>',unsafe_allow_html=True)
                st.caption('Следующий шаг: '+own_recs.iloc[0].action)
            action=own_recs.iloc[0].action if len(own_recs) else 'Хочу уточнить ваши потребности и обсудить следующий заказ.'
            with st.expander('Модель AI и подготовка текста'):
                model_picker(store,cid,c,own_recs)
            st.markdown('**Готовое сообщение для клиента**')
            draft=st.text_area('Черновик сообщения',store.get('draft',cid,message(c.company,action)),key=f'client_draft_{cid}',height=225,label_visibility='collapsed')
            st.caption(f'{len(draft)} символов · черновик можно редактировать')
            save_col,copy_col=st.columns([1,1],gap='small')
            with save_col:
                if st.button('Сохранить черновик',width='stretch',type='primary'): save_record('draft',cid,draft)
            with copy_col: st.download_button('Скачать текст',draft,file_name='message.txt',width='stretch')
            with st.expander('Скопировать сообщение'):
                st.code(draft,language=None)
                st.caption('Кнопка копирования — справа. Отправка выполняется менеджером вручную.')
            wa,tg=st.columns(2,gap='small')
            with wa,st.container(key='send-whatsapp'): st.link_button('WhatsApp ↗','https://web.whatsapp.com/',width='stretch')
            with tg,st.container(key='send-telegram'): st.link_button('Telegram ↗','https://web.telegram.org/',width='stretch')
            st.caption('Откроется мессенджер. Сначала скопируйте текст; сообщение автоматически не отправляется.')
            with st.container(border=True,key='contact-task'):
                st.markdown('**▢ Создать задачу**')
                with st.form(f'task_card_{cid}'):
                    date_col,add_col=st.columns([1.2,1],gap='small',vertical_alignment='bottom')
                    with date_col: due_date=st.date_input('Следующий контакт',TODAY+timedelta(days=5),key=f'due_card_{cid}')
                    with add_col: submitted=st.form_submit_button('Создать задачу',type='primary',width='stretch')
                    with st.expander('Название и заметка'):
                        title=st.text_input('Задача',action,key=f'title_card_{cid}')
                        note=st.text_area('Заметка',key=f'note_card_{cid}',height=68)
                    if submitted:
                        try:
                            store.add(cid,title,due_date,note)
                            st.success('Задача сохранена в вашем плане контактов.')
                        except (ValueError,StoreError): st.error('Не удалось сохранить задачу. Проверьте название и доступность базы.')
elif page == 'Возврат клиентов':
    st.write('Клиенты с задержкой более 1,5 индивидуального цикла. Фиксированный порог дней не применяется.')
    late = summary[summary.cycle_ratio > 1.5].sort_values('cycle_ratio',ascending=False)
    st.dataframe(late[['company','last_order','days_since','cycle','cycle_ratio']].rename(columns={'company':'Клиент','last_order':'Последняя покупка','days_since':'Дней без заказа','cycle':'Обычный цикл, дн.','cycle_ratio':'Отклонение, ×'}),hide_index=True,width='stretch')
    st.caption('Клиенты с недостаточной историей не классифицируются как потерянные. Задержка — сигнал для разговора, а не подтверждение потери клиента.')
    recommendation_cards(recommendations[recommendations.kind == 'return'])
elif page == 'Товарная аналитика':
    cats = st.multiselect('Категории',products.category.unique())
    frame = selected[selected.category.isin(cats)] if cats else selected
    kpis(frame)
    graph(frame)
    if not frame.empty:
        category = frame.groupby('category',as_index=False).revenue.sum().rename(columns={'category':'Категория','revenue':'Оборот, ₽'})
        st.plotly_chart(px.bar(category,x='Категория',y='Оборот, ₽',color_discrete_sequence=['#14946B']),width='stretch')
        st.subheader('Популярные товары')
        st.dataframe(frame.groupby('product',as_index=False)[['quantity','revenue','profit']].agg(lambda v: v.sum() if v.notna().all() else float('nan')).sort_values('revenue',ascending=False).rename(columns={'product':'Товар','quantity':'Количество','revenue':'Оборот, ₽','profit':'Валовая прибыль, ₽'}),hide_index=True,width='stretch')
        st.subheader('Сопутствующие покупки')
        st.caption('Число заказов, в которых встречаются оба товара. Это совместные покупки, а не доказательство причинной связи.')
        st.dataframe(companions(frame).head(20),hide_index=True,width='stretch')
elif page == 'AI-рекомендации':
    st.info('Работают правила Python без платного API. Объяснения основаны на вычислениях, предложения требуют проверки менеджером.')
    pr = st.multiselect('Приоритет рекомендаций',['Высокий','Средний'])
    kinds = {'return':'Возврат','cross':'Сопутствующие товары','decline':'Снижение оборота','growth':'Рост среднего чека'}
    kind = st.selectbox('Тип рекомендации',['Все']+list(kinds.values()))
    frame = recommendations
    if pr: frame = frame[frame.priority.isin(pr)]
    if kind != 'Все': frame = frame[frame.kind == next(k for k,v in kinds.items() if v == kind)]
    st.caption(f'Найдено: {len(frame)}. Рекомендации используют всю историю.')
    offset = st.number_input('Начиная с рекомендации',min_value=1,max_value=max(1,len(frame)),value=1,step=15)
    recommendation_cards(frame.iloc[int(offset)-1:],15)
elif page == 'Задачи':
    st.subheader('Новый контакт')
    cid = client_picker('task_client')
    task_form(cid,'new')
    st.subheader('План контактов')
    status_filter = st.multiselect('Статусы задач',['Запланирована','В работе','Выполнена','Отменена'])
    tasks = store.tasks().merge(clients[['client_id','company']],on='client_id',how='left')
    if status_filter: tasks = tasks[tasks.status.isin(status_filter)]
    if tasks.empty:
        st.info('Задач с выбранными условиями нет.')
    for task in tasks.itertuples():
        with st.expander(f'#{task.id} · {task.company} · {task.title} · {task.due}'):
            with st.form(f'edit_{task.id}'):
                statuses = ['Запланирована','В работе','Выполнена','Отменена']
                status = st.selectbox('Статус',statuses,index=statuses.index(task.status),key=f'status_{task.id}')
                note = st.text_area('Заметка о результате',task.note,key=f'result_{task.id}')
                if st.form_submit_button('Сохранить изменения'):
                    try:
                        store.update(task.id,status,note)
                        st.rerun()
                    except StoreError: st.error('Не удалось сохранить результат задачи.')
elif page == 'Эффективность':
    st.subheader('Продажи за выбранный период · ' + source)
    kpis(selected)
    graph(selected)
    st.subheader('Работа менеджера · локальные действия')
    processed = store.processed()
    count = len(processed[(pd.to_datetime(processed.processed_at).dt.date >= start) & (pd.to_datetime(processed.processed_at).dt.date <= end)]) if len(processed) else 0
    tasks = store.tasks()
    a,b,c = st.columns(3)
    a.metric('Обработано рекомендаций за период',count)
    b.metric('Создано задач · всего',len(tasks))
    c.metric('Выполнено задач · всего',int((tasks.status == 'Выполнена').sum()))
    st.info('Источник продаж: ' + source + '. Связь рекомендаций с заказами не отслеживается: выручка и прибыль не приписываются действиям менеджера.')

elif page=='Сообщения':
    st.subheader('Подготовка сообщений')
    st.write('Черновики сохраняются в карточке клиента кнопкой «Сохранить черновик». Копируйте текст и отправляйте через свой мессенджер.')
    st.info('Проверка подключения WhatsApp, Telegram и MAX доступна в Настройках. Входящие сообщения и отправка через API ещё не реализованы.')
    st.download_button('Экспорт моих записей',store.export(),file_name='sales-records.json',mime='application/json')
