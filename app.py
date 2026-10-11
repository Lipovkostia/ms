from datetime import timedelta
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
from sales_center.analytics import metrics, orders, client_summary, period, monthly, companions
from sales_center.recommendations import generate, message
from sales_center.storage import Store, StoreError
from sales_center.moysklad import MoySkladError
from sales_center.sync import refresh, due
from sales_center.identity import identity
from sales_center.theme import CSS
from sales_center.settings import connections, model_picker

st.set_page_config(page_title='AI Sales Center', page_icon='📈', layout='wide')
st.markdown(CSS,unsafe_allow_html=True)
TODAY=pd.Timestamp.now(tz='Europe/Moscow').date()
user_id,user_name=identity()
PAGES=['Главная','Клиенты','Карточка клиента','Возврат клиентов','Товарная аналитика','AI-рекомендации','Задачи','Эффективность','Сообщения','Настройки']
with st.sidebar:
    st.markdown('<div class="brand">◈ AI-Помощник</div><div class="brand-sub">для оптовых продаж</div>',unsafe_allow_html=True)
    page=st.radio('Раздел',PAGES,key='page')
    st.divider()
    st.caption(user_name)
    if user_id=='personal': st.warning('Персональный режим. Для сотрудников настройте вход в Настройках.')
    else:
        if st.button('Выйти'): st.logout()

@st.fragment(run_every='60s')
def sync_panel():
    interval=st.session_state.get('sync_interval',0)
    auto=due(st.session_state,interval)
    with st.expander('Мой Склад · подключение и обновление',expanded='live_data' not in st.session_state):
        with st.form('moysklad_connect',clear_on_submit=True):
            token=st.text_input('API-токен Моего Склада',type='password')
            retain=st.checkbox('Держать токен в памяти этой сессии для обновления')
            requested=st.form_submit_button('Загрузить / обновить данные')
        interval=st.selectbox('Период обновления (минут)',[0,15,30,60],format_func=lambda n:'Только вручную' if n==0 else f'Каждые {n} минут',key='sync_interval')
        st.caption('Полная загрузка 12 месяцев может занять несколько минут. Автообновление работает только при открытой вкладке и токене в памяти; проверка таймера раз в минуту. Это снимок данных, а не поток в реальном времени.')
        if interval and not st.session_state.get('sync_token') and not (requested and retain): st.info('Для автообновления загрузите данные с флажком хранения токена в сессии.')
        if requested or auto:
            try:
                with st.status('Подключение…',expanded=True) as status:
                    def report(stage,count,total): status.update(label=f'{stage}: {count:,} / {total:,}' if total else stage)
                    fresh=refresh(st.session_state,pd.Timestamp.now(tz='Europe/Moscow').date(),token=token if requested else None,progress=report,retain=retain if requested else True)
                    status.update(label='Данные проверены и загружены',state='complete',expanded=False)
                st.success(f'Подключение выполнено: {len(fresh[0]):,} клиентов, {fresh[2].order_id.nunique():,} отгрузок.')
                st.rerun()
            except MoySkladError as exc: st.session_state.live_error=str(exc)
            except (KeyError,TypeError,ValueError) as exc: st.session_state.live_error=f'Ошибка обработки данных ({type(exc).__name__}). Прежние данные сохранены. Сообщите этот код администратору.'
        if st.session_state.get('live_error'): st.error(st.session_state.live_error)
        if st.session_state.get('sync_success_at'):
            stamp=pd.Timestamp(st.session_state.sync_success_at,unit='s',tz='UTC').tz_convert('Europe/Moscow')
            st.caption(f'Успешное обновление: {stamp:%d.%m.%Y %H:%M} МСК')
        if st.button('Отключить источник и очистить сессию'):
            for key in list(st.session_state):
                if key.startswith(('live_','sync_','provider_','client_draft_','draft_')): del st.session_state[key]
            st.rerun()
sync_panel()
st.title(page)
source='Мой Склад'
if page=='Настройки':
    connections()
    st.stop()
if 'live_data' not in st.session_state:
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
    try: database_url=st.secrets.get('DATABASE_URL')
    except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError): database_url=None
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
st.caption('Реальные проведённые отгрузки за 12 месяцев · RUB · оборот без НДС и без вычета возвратов. Данные обновляются только после успешной синхронизации.')
if not store.persistent: st.caption('Записи: локальная SQLite. Streamlit Cloud может удалить их при перезапуске; для постоянного хранения настройте PostgreSQL.')
st.caption(f'Исключено внутренних отгрузок: {lines.attrs.get("excluded_internal_shipments",0)} · пустых документов: {lines.attrs.get("excluded_empty_shipments",0)}')
if lines.cost.isna().any(): st.warning('API не вернул себестоимость части позиций. Валовая прибыль соответствующих периодов недоступна.')
with st.expander('Период аналитики'):
    start=st.date_input('Начало периода',TODAY-timedelta(days=90),key='period_start')
    end=st.date_input('Конец периода',TODAY,key='period_end')
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
    top=st.columns(4)
    top[0].metric('Всего клиентов',len(clients))
    top[1].metric('С покупками за 12 месяцев',int((summary.order_count>0).sum()))
    top[2].metric('Заказ задерживается',int((summary.cycle_ratio>1.5).sum()))
    top[3].metric('Возможности для контакта',len(recommendations))
    left,center,right=st.columns([1.05,1.65,1.3],gap='medium')
    with left:
        st.subheader('Приоритетные клиенты')
        search=st.text_input('Поиск по названию компании или городу')
        priorities=st.multiselect('Приоритет',['Высокий','Средний','Низкий'])
        view=summary[summary.company.str.contains(search,case=False,regex=False)|summary.city.str.contains(search,case=False,regex=False)]
        if priorities: view=view[view.priority.isin(priorities)]
        view=view.assign(rank=view.priority.map({'Высокий':0,'Средний':1,'Низкий':2})).sort_values(['rank','revenue'],ascending=[True,False])
        st.caption(f'Найдено: {len(view)} · оборот за 12 месяцев')
        if view.empty: st.info('Клиенты не найдены.'); st.stop()
        ids=view.client_id.tolist()
        if st.session_state.get('workspace_client') not in ids: st.session_state.workspace_client=ids[0]
        cid=st.selectbox('Выберите клиента',ids,format_func=lambda x:clients.set_index('client_id').loc[x,'company'],key='workspace_client')
        if st.session_state.get('client_list_page',1)>max(1,(len(view)+5)//6): st.session_state.client_list_page=1
        offset=st.number_input('Страница клиентов',min_value=1,max_value=max(1,(len(view)+5)//6),value=1,key='client_list_page')
        for item in view.iloc[(offset-1)*6:offset*6].itertuples():
            with st.container(border=True):
                st.button(item.company,key=f'pick_{item.client_id}',on_click=lambda value: st.session_state.update(workspace_client=value),args=(item.client_id,),width='stretch')
                st.caption(item.priority+' · '+item.city)
                st.write(rub(item.revenue))
                st.caption('Последний заказ: '+(item.last_order.strftime('%d.%m.%Y') if pd.notna(item.last_order) else 'нет покупок'))
        with st.expander('Таблица клиентов'):
            st.dataframe(view[['company','city','revenue','last_order','priority']].rename(columns={'company':'Клиент','city':'Город','revenue':'Оборот, ₽','last_order':'Последняя покупка','priority':'Приоритет'}),hide_index=True)
    c=summary.set_index('client_id').loc[cid]
    own=period(lines[lines.client_id==cid],start,end)
    with center:
        st.subheader(c.company)
        st.caption(c.city+' · '+c.priority+' приоритет')
        tabs=st.tabs(['Обзор','История','Товары','Заметки','Контакты'])
        with tabs[0]:
            m=metrics(own)
            a,b=st.columns(2)
            a.metric('Оборот за период',rub(m['revenue']))
            b.metric('Средний чек',rub(m['average']))
            st.write(f'Частота: {c.frequency:.1f} заказа за 30 дней')
            st.write('Обычный цикл (медиана): '+(f'{c.cycle:.0f} дней' if pd.notna(c.cycle) else 'недостаточно истории'))
            st.caption('Цикл определяется при ≥3 заказах; частота = количество заказов × 30 / дней с первого заказа до сегодня.')
            graph(own)
            if not own.empty:
                cat=own.groupby('category',as_index=False).revenue.sum()
                st.plotly_chart(px.pie(cat,names='category',values='revenue',hole=.65,color_discrete_sequence=['#10b981','#60a5fa','#fbbf24','#a78bfa']),width='stretch')
        with tabs[1]: st.dataframe(orders(own).sort_values('date',ascending=False).drop(columns='client_id').rename(columns={'order_id':'Отгрузка','date':'Дата','revenue':'Оборот, ₽','cost':'Себестоимость, ₽','profit':'Валовая прибыль, ₽'}),hide_index=True)
        with tabs[2]: st.dataframe(own.groupby('product',as_index=False).agg(quantity=('quantity','sum'),revenue=('revenue','sum'),orders=('order_id','nunique')).rename(columns={'product':'Товар','quantity':'Количество','revenue':'Оборот, ₽','orders':'Заказов'}),hide_index=True)
        with tabs[3]:
            note=st.text_area('Заметка о клиенте',store.get('note',cid,''),key=f'client_note_{cid}')
            if st.button('Сохранить заметку'): save_record('note',cid,note)
        with tabs[4]:
            contact=clients.set_index('client_id').loc[cid]
            st.write('Телефон: '+str(contact.get('phone') or 'не указан'))
            st.write('Email: '+str(contact.get('email') or 'не указан'))
    with right:
        st.subheader('✦ AI-рекомендации')
        own_recs=recommendations[recommendations.client_id==cid]
        for r in own_recs.head(3).itertuples():
            with st.container(border=True):
                st.markdown('**'+r.title+'**')
                st.write(r.reason)
                st.caption(r.priority+' · потенциальный оборот '+rub(r.effect)+' (оценка)')
                st.write(r.action)
        if own_recs.empty: st.info('Сигналов по истории покупок пока нет.')
        action=own_recs.iloc[0].action if len(own_recs) else 'Хочу уточнить ваши потребности и обсудить следующий заказ.'
        model_picker(store,cid,c,own_recs)
        draft=st.text_area('Черновик сообщения',store.get('draft',cid,message(c.company,action)),key=f'client_draft_{cid}',height=220)
        if st.button('Сохранить черновик'): save_record('draft',cid,draft)
        st.code(draft,language=None)
        st.caption('Кнопка копирования — справа в блоке. Отправка только вручную; автоматической рассылки нет.')
        task_form(cid,f'card_{cid}',action)
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
