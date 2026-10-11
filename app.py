from datetime import date, timedelta
from pathlib import Path
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st
from sales_center.data import demo_data
from sales_center.analytics import metrics, orders, client_summary, period, monthly, companions
from sales_center.recommendations import generate, message
from sales_center.storage import Store
from sales_center.live_data import load_live
from sales_center.moysklad import MoySkladError

st.set_page_config(page_title='AI Sales Center', page_icon='📈', layout='wide')
st.markdown('''<style>
[data-testid="stSidebar"]{background:#142b49;color:white}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] p,[data-testid="stSidebar"] label{color:white}
[data-testid="stMetric"]{background:white;padding:18px;border-radius:14px;box-shadow:0 3px 14px #152b4910;border:1px solid #e6edf5}
h1,h2,h3{letter-spacing:-.025em} .block-container{padding-top:2rem;max-width:1500px}
[data-testid="stExpander"]{background:white;border-radius:12px}
[data-testid="stSidebar"] [data-testid="stExpander"]{background:#1e3858}
@media(max-width:640px){.block-container{padding:1rem}.stMetric{min-width:130px}}
</style>''', unsafe_allow_html=True)
TODAY = pd.Timestamp.now(tz='Europe/Moscow').date()
@st.cache_data
def load(today):
    return demo_data(today)
with st.sidebar:
    source = st.selectbox('Источник данных', ['Демонстрационные данные', 'Мой Склад'])
    if source == 'Мой Склад':
        st.caption('Только чтение проведённых отгрузок в RUB за 12 месяцев. Возвраты не вычитаются. Выручка без НДС.')
        with st.form('moysklad_connect', clear_on_submit=True):
            token = st.text_input('API-токен Моего Склада', type='password', help='Токен передаётся только API Моего Склада. В файлы и базу он не записывается. После отправки поле очищается.')
            st.caption('При пустом поле используется MOYSKLAD_TOKEN из окружения. Для обновления введите токен заново.')
            connect = st.form_submit_button('Загрузить / обновить данные')
        if connect:
            try:
                with st.spinner('Загрузка контрагентов, товаров и отгрузок…'):
                    fresh = load_live(TODAY, token=token)
                st.session_state.live_data = fresh
                st.session_state.live_loaded = pd.Timestamp.now(tz='Europe/Moscow').strftime('%d.%m.%Y %H:%M МСК')
            except MoySkladError as exc:
                st.error(str(exc))
            except (KeyError, TypeError, ValueError):
                st.error('Получены неподдерживаемые данные API. Загрузка отменена; прежние данные сохранены.')
if source == 'Мой Склад':
    if 'live_data' not in st.session_state:
        st.title('Подключение Моего Склада')
        st.info('В боковой панели вставьте новый API-токен в поле «API-токен Моего Склада» и нажмите «Загрузить / обновить данные». После успешной загрузки появятся разделы с данными вашего аккаунта.')
        st.stop()
    clients, products, lines = st.session_state.live_data
else:
    clients, products, lines = load(TODAY)
if clients.empty:
    st.info('Источник не содержит клиентов. Проверьте доступ и данные.')
    st.stop()
summary = client_summary(clients, lines, TODAY)
recommendations = generate(summary, lines, products, TODAY)
try:
    store = Store(Path(__file__).parent/'.runtime'/('sales.db' if source == 'Демонстрационные данные' else 'moysklad.db'))
except (sqlite3.Error, OSError):
    st.error('Не удалось открыть базу задач. Проверьте право записи в папку .runtime.')
    st.stop()
PAGES = ['Главная', 'Клиенты', 'Карточка клиента', 'Возврат клиентов', 'Товарная аналитика', 'AI-рекомендации', 'Задачи', 'Эффективность']
if 'page' not in st.session_state:
    st.session_state.page = 'Главная'
with st.sidebar:
    st.title('AI Sales Center')
    st.caption('Персональный центр продаж')
    page = st.radio('Раздел', PAGES, key='page')
    st.divider()
    st.caption('Источник: ' + source)
    with st.expander('Об интеграции'):
        st.write('API используется только для чтения отгрузок. Задачи демонстрационного и реального режимов хранятся отдельно. Ключи не вводятся в приложение.')
st.title(page)
if source == 'Демонстрационные данные':
    st.caption('ДЕМОНСТРАЦИОННЫЙ РЕЖИМ · Все компании, заказы и финансовые показатели вымышлены. Задачи сохраняются локально в SQLite.')
else:
    st.caption('МОЙ СКЛАД · Загружено: ' + st.session_state.live_loaded + '. Проведённые отгрузки в RUB, выручка без НДС, без вычета возвратов. Это показатели отгрузок, а не чистых продаж.')
    if lines.cost.isna().any():
        st.warning('Для части позиций API не вернул себестоимость. Итоги валовой прибыли и маржинальности не рассчитываются для таких периодов.')
with st.expander('Период аналитики', expanded=False):
    start = st.date_input('Начало периода', TODAY-timedelta(days=90), key='period_start')
    end = st.date_input('Конец периода', TODAY, key='period_end')
if start > end:
    st.error('Начало периода не может быть позже конца.')
    st.stop()
selected = period(lines, start, end)

def rub(value):
    return f'{value:,.0f} ₽'.replace(',', ' ') if pd.notna(value) else 'Нет данных'

def open_client(cid):
    st.session_state.client_id = int(cid)
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
            except (ValueError,sqlite3.Error) as exc:
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
            draft = st.text_area('Черновик сообщения — можно редактировать', message(r.company,r.action), key=f'draft_{r.id}')
            st.code(draft, language=None)
            st.caption('Используйте кнопку копирования справа в блоке текста. Сообщения не отправляются.')
            st.download_button('Скачать черновик', draft, file_name='message.txt', key=f'dl_{r.id}')
            task_form(r.client_id,r.id,r.action,r.id)
            if r.id in processed:
                st.success('Рекомендация обработана менеджером')
            elif st.button('Отметить обработанной', key=f'process_{r.id}'):
                store.process(r.id)
                st.rerun()

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
elif page == 'Клиенты':
    search = st.text_input('Поиск по названию компании или городу')
    a,b = st.columns(2)
    seg = a.multiselect('Сегменты', sorted(clients.segment.unique()))
    priorities = b.multiselect('Приоритет', ['Высокий','Средний','Низкий'])
    view = summary.copy()
    amount = selected.groupby('client_id').revenue.sum()
    view['revenue'] = view.client_id.map(amount).fillna(0)
    view = view[view.company.str.contains(search,case=False,regex=False) | view.city.str.contains(search,case=False,regex=False)]
    if seg: view = view[view.segment.isin(seg)]
    if priorities: view = view[view.priority.isin(priorities)]
    st.caption('Оборот за выбранный период. Последняя покупка и приоритет — по всей истории.')
    st.dataframe(view[['company','segment','city','revenue','last_order','priority']].rename(columns={'company':'Клиент','segment':'Сегмент','city':'Город','revenue':'Оборот, ₽','last_order':'Последняя покупка','priority':'Приоритет'}),hide_index=True,width='stretch')
    if view.empty:
        st.info('Клиенты не найдены. Измените фильтры.')
    else:
        cid = st.selectbox('Открыть клиента из списка',view.client_id.tolist(),format_func=lambda x: clients.set_index('client_id').loc[x,'company'])
        st.button('Открыть карточку клиента',on_click=open_client,args=(cid,))
elif page == 'Карточка клиента':
    cid = client_picker('card_client')
    c = summary.set_index('client_id').loc[cid]
    st.subheader(c.company)
    st.caption(f'{c.segment} · {c.city}')
    own = lines[lines.client_id == cid]
    kpis(period(own,start,end))
    cycle = f'{c.cycle:.0f} дней' if pd.notna(c.cycle) else 'Недостаточно истории'
    mean = f'{c.mean_gap:.1f} дней' if pd.notna(c.mean_gap) else 'Нет повторных заказов'
    st.write(f'Обычный цикл (медиана): **{cycle}** · Средний интервал: **{mean}** · Частота: **{c.frequency:.1f} заказа за 30 дней**.')
    st.caption('Цикл и частота рассчитаны по всей истории. Частота = число заказов × 30 / дней от первого заказа до сегодня (минимум 1 день). Цикл определяется при наличии минимум трёх заказов.')
    graph(period(own,start,end))
    st.subheader('Популярные категории за период')
    client_period = period(own,start,end)
    category_stats = client_period.groupby('category',as_index=False).agg(order_count=('order_id','nunique'),revenue=('revenue','sum'))
    st.dataframe(category_stats.sort_values('order_count',ascending=False).rename(columns={'category':'Категория','order_count':'Заказов с категорией','revenue':'Оборот, ₽'}),hide_index=True,width='stretch')
    st.subheader('Чаще всего покупает')
    product_stats = client_period.groupby('product',as_index=False).agg(order_count=('order_id','nunique'),quantity=('quantity','sum'),revenue=('revenue','sum'))
    st.dataframe(product_stats.sort_values('order_count',ascending=False).rename(columns={'product':'Товар','order_count':'Заказов с товаром','quantity':'Количество','revenue':'Оборот, ₽'}),hide_index=True,width='stretch')
    st.subheader('История заказов за период')
    st.dataframe(orders(period(own,start,end)).sort_values('date',ascending=False).rename(columns={'order_id':'Заказ','date':'Дата','revenue':'Оборот, ₽','cost':'Себестоимость, ₽','profit':'Валовая прибыль, ₽'}).drop(columns='client_id'),hide_index=True,width='stretch')
    st.subheader('Следующий контакт')
    draft = st.text_area('Черновик сообщения',message(c.company,'Хочу уточнить ваши потребности и предложить подходящий ассортимент.'),key=f'client_draft_{cid}')
    st.code(draft,language=None)
    st.caption('Кнопка копирования доступна в блоке текста. Отправка выполняется менеджером самостоятельно.')
    task_form(cid,f'card_{cid}')
    st.subheader('Рекомендации по клиенту')
    recommendation_cards(recommendations[recommendations.client_id == cid],5)
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
                    store.update(task.id,status,note)
                    st.rerun()
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
