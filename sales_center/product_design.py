"""Two-panel product workspace: shared filters, actual sales and buyer navigation."""
import hashlib
import pandas as pd
import streamlit as st
from .presentation import safe, money
from .product_analytics import price_types, price_list, category_paths, buyers
from .product_design_data import PERIODS, period_window, filter_sales, catalog_view, warehouse_options, export_catalog_csv

SORTS={'revenue':'По продажам','name':'По названию','price':'По цене','quantity':'По объёму'}


def reset_filters():
    st.session_state.update(price_category=None,price_search='',pd_buyer=None,pd_warehouse=None,pd_only_sales=True,positive_prices=True,pd_period='12m',pd_period_quick='12m',pd_sort='revenue',price_product_page=1,price_buyer_page=1)
    st.session_state.pop('pd_category_search',None)


def change_period(source):
    other='pd_period_quick' if source=='pd_period' else 'pd_period'
    st.session_state[other]=st.session_state[source]
    st.session_state.price_product_page=1
    st.session_state.price_buyer_page=1


def select_product(pid):
    st.session_state.price_product_id=int(pid)
    st.session_state.pd_product_selector=int(pid)
    st.session_state.price_buyer_page=1


def table_key(prefix,ids,context):
    fingerprint=hashlib.sha256(repr((tuple(ids),context)).encode()).hexdigest()[:14]
    return prefix+'_'+fingerprint


def selected_row(key,frame,action):
    state=st.session_state.get(key,{})
    selection=state.get('selection',{})
    rows=selection.get('rows',[])
    if rows and 0<=rows[0]<len(frame): action(int(frame.iloc[rows[0]][frame.columns[0]]))


def compact(value):
    if abs(value)>=1_000_000: return f'{value/1_000_000:.2f} млн'.replace('.',',')
    if abs(value)>=100_000: return f'{value/1000:.1f} тыс.'.replace('.',',')
    return f'{value:,.2f}'.rstrip('0').rstrip('.').replace(',',' ').replace('.',',')


def price_label(amount,currency):
    value=f'{amount:,.2f}'.replace(',',' ').replace('.',',')
    if value.endswith(',00'): value=value[:-3]
    return value+' '+('₽' if currency=='RUB' else currency)


def render(products,clients,lines,today,start,end,on_client,on_catalog_refresh):
    with st.container(key='product-design-page'):
        with st.container(key='product-design-header'):
            text_col,tools_col=st.columns([1.2,1],gap='medium',vertical_alignment='bottom')
        with text_col,st.container(key='product-design-heading'):
            st.markdown('<div class="pd-eyebrow">Аналитика продаж</div>',unsafe_allow_html=True)
            st.title('Товарная аналитика')
            st.markdown('<div class="pd-subtitle">Спрос, продажи и покупатели по каждому товару</div>',unsafe_allow_html=True)
        types=price_types(products)
        if not types:
            st.info('В сохранённом снимке нет типов цен. Загрузите текущий прайс-лист: история покупок останется на месте.')
            if st.button('Загрузить текущий прайс-лист',key='load_price_catalog'): on_catalog_refresh()
            return
        if st.session_state.get('price_type') not in types:
            st.session_state.price_type=next((k for k,n in types.items() if n=='Цена опт безнал'),next(iter(types)))
        with tools_col,st.container(key='product-design-controls'):
            price_col,export_col,refresh_col=st.columns([2,1,1],gap='small',vertical_alignment='bottom')
            with price_col: price_type=st.selectbox('Прайс-лист',list(types),format_func=types.get,key='price_type')
            with export_col: export_slot=st.empty()
            with refresh_col:
                if st.button('↻ Обновить',key='refresh_price_catalog',width='stretch',help='Загрузить текущие товары и цены из Моего Склада'): on_catalog_refresh()
        if st.session_state.get('pd_period') not in PERIODS: st.session_state.pd_period='12m'
        if 'pd_period_quick' not in st.session_state: st.session_state.pd_period_quick=st.session_state.pd_period
        warehouses=warehouse_options(lines)
        if st.session_state.get('pd_warehouse') not in warehouses: st.session_state.pd_warehouse=None
        buyer_names=clients.set_index('client_id').company.to_dict()
        if st.session_state.get('pd_buyer') not in buyer_names: st.session_state.pd_buyer=None
        categories=[None]+category_paths(price_list(products,price_type,positive=False))
        if 'price_category' not in st.session_state or st.session_state.get('price_category') not in categories: st.session_state.price_category=None
        with st.container(key='product-design-filters'):
            category_col,warehouse_col,period_col,buyer_col,sales_col,reset_col=st.columns([1.2,1,1.2,1.2,1.2,.8],gap='small')
            with category_col,st.popover('Категория: '+(st.session_state.price_category or 'Все'),use_container_width=True):
                cq=st.text_input('Найти категорию',key='pd_category_search')
                available=[p for p in categories if p is None or cq.casefold() in p.casefold() or p==st.session_state.price_category]
                st.selectbox('Категории прайс-листа',available,format_func=lambda p:'Все категории' if p is None else '　'*p.count('/')+p,key='price_category')
                st.checkbox('Только товары с ненулевой ценой',value=True,key='positive_prices')
            with warehouse_col,st.popover('Склад: '+(warehouses.get(st.session_state.pd_warehouse) or 'Все'),use_container_width=True):
                st.selectbox('Склад отгрузки',[None]+list(warehouses),format_func=lambda w:warehouses.get(w,'Все склады'),key='pd_warehouse',disabled=not bool(warehouses))
                if not warehouses: st.caption('В текущей загрузке нет разбивки отгрузок по складам. Показаны все доступные отгрузки.')
            with period_col,st.popover('Период: '+PERIODS[st.session_state.pd_period],use_container_width=True):
                st.radio('Период продаж',list(PERIODS),format_func=PERIODS.get,key='pd_period',on_change=change_period,args=('pd_period',))
            with buyer_col,st.popover('Покупатель: '+str(buyer_names.get(st.session_state.pd_buyer,'Все')),use_container_width=True):
                st.selectbox('Покупатель',[None]+list(buyer_names),format_func=lambda cid:buyer_names.get(cid,'Все покупатели'),key='pd_buyer')
            with sales_col: only_sales=st.checkbox('Только с продажами',value=True,key='pd_only_sales')
            with reset_col: st.button('Сбросить',key='pd_reset',on_click=reset_filters,width='stretch')
        beginning,ending=period_window(lines,today,st.session_state.pd_period)
        sales=filter_sales(lines,beginning,ending,st.session_state.pd_buyer,st.session_state.pd_warehouse)
        chips=[st.session_state.price_category or 'Все категории',PERIODS[st.session_state.pd_period],buyer_names.get(st.session_state.pd_buyer,'Все покупатели')]
        if st.session_state.pd_warehouse is not None: chips.append(warehouses[st.session_state.pd_warehouse])
        st.markdown(' '.join('<span class="pd-chip">'+safe(chip)+'</span>' for chip in chips),unsafe_allow_html=True)
        st.caption(f'История: {beginning:%d.%m.%Y}–{ending:%d.%m.%Y}. «Весь доступный период» использует загруженную годовую историю. Суммы без НДС, без вычета возвратов; прайс не подтверждает наличие.')
        with st.container(key='product-design-workspace'):
            catalog_col,details_col=st.columns([1.02,1],gap='medium')
            with catalog_col,st.container(key='product-design-catalog'):
                st.subheader('Товары')
                search_col,sort_col=st.columns([1.7,1],gap='small')
                with search_col: query=st.text_input('Поиск товара',placeholder='Название, код или артикул',key='price_search',label_visibility='collapsed')
                with sort_col: sort=st.selectbox('Сортировка товаров',list(SORTS),format_func=SORTS.get,key='pd_sort',label_visibility='collapsed')
                view=catalog_view(products,sales,price_type,st.session_state.price_category,query,only_sales,sort,st.session_state.get('positive_prices',True))
                st.caption(f'{len(view):,} позиций · {types[price_type]}')
                export_slot.download_button('⇩ Экспорт',export_catalog_csv(view),file_name='product_analytics.csv',mime='text/csv',key='pd_export',width='stretch',disabled=view.empty)
                if view.empty:
                    st.info('Нет товаров по выбранным условиям. Измените поиск или сбросьте фильтры.')
                    st.button('Сбросить фильтры',key='pd_empty_reset',on_click=reset_filters)
                else:
                    ids=view.product_id.tolist()
                    if st.session_state.get('price_product_id') not in ids: select_product(ids[0])
                    selected=st.session_state.price_product_id
                    pages=max(1,(len(view)+6)//7)
                    if st.session_state.get('price_product_page',1)>pages: st.session_state.price_product_page=1
                    page=st.session_state.get('price_product_page',1)
                    current=view.iloc[(page-1)*7:page*7].reset_index(drop=True)
                    displayed=pd.DataFrame({'ТОВАР':current['product'],'АРТИКУЛ':current.get('article',pd.Series('',index=current.index)),'КАТЕГОРИЯ':current.category,'ЦЕНА':[price_label(row.list_price,row.currency) for row in current.itertuples()],'ПРОДАНО':[f'{row.sold_quantity:g} {getattr(row,"unit","ед. товара")}' for row in current.itertuples()]})
                    styles=displayed.style.apply(lambda r:['background-color: #E8F5F2; color: #078B76' if current.iloc[r.name].product_id==selected else '' for _ in r],axis=1)
                    key=table_key('pd_products',current.product_id,(price_type,beginning,ending,st.session_state.pd_buyer,st.session_state.pd_warehouse))
                    st.dataframe(styles,hide_index=True,width='stretch',height=min(560,55+50*len(current)),row_height=50,key=key,on_select=lambda table=key,rows=current[['product_id']]:selected_row(table,rows,select_product),selection_mode='single-row',column_config={name:st.column_config.TextColumn(width='medium' if name=='ТОВАР' else 'small') for name in displayed.columns})
                    footer,pager=st.columns([2,1],vertical_alignment='center')
                    footer.caption(f'Показано {(page-1)*7+1}–{min(page*7,len(view))} из {len(view)} · нажмите строку товара')
                    pager.number_input('Страница товаров',min_value=1,max_value=pages,key='price_product_page',label_visibility='collapsed')
                    with st.expander('Выбрать товар из списка'):
                        if st.session_state.get('pd_product_selector') not in ids: st.session_state.pd_product_selector=selected
                        st.selectbox('Активный товар',ids,format_func=lambda pid:view.set_index('product_id').loc[pid,'product'],key='pd_product_selector',on_change=lambda:select_product(st.session_state.pd_product_selector))
            with details_col,st.container(key='product-design-details'):
                st.subheader('Аналитика товара')
                if view.empty:
                    st.info('Выберите товар после изменения фильтров. Его покупатели и показатели появятся здесь.')
                    return
                product=view.set_index('product_id').loc[st.session_state.price_product_id]
                st.markdown('<div class="pd-selected-label">Выбранный товар · Артикул '+safe(product.get('article') or 'не указан')+'</div><div class="pd-product-title">'+safe(product['product'])+'</div><div class="pd-product-meta">'+safe(product.category)+' · '+safe(types[price_type])+' · '+safe(price_label(product.list_price,product.currency)+' / '+product.get('unit','ед. товара'))+'</div>',unsafe_allow_html=True)
                with st.container(key='product-design-period'):
                    st.segmented_control('Быстрый период',list(PERIODS),format_func=PERIODS.get,key='pd_period_quick',required=True,label_visibility='collapsed',on_change=change_period,args=('pd_period_quick',))
                stats=buyers(sales,clients,int(st.session_state.price_product_id),today)
                with st.container(key='product-design-metrics'):
                    a,b,c=st.columns(3,gap='small')
                    a.metric('Покупателей',len(stats))
                    b.metric('Сумма покупок',compact(stats.revenue.sum())+' ₽',help=money(stats.revenue.sum()))
                    c.metric('Проданный объём',compact(stats.quantity.sum())+' '+product.get('unit','ед. товара'),help=f'{stats.quantity.sum():g} {product.get("unit","ед. товара")}')
                st.markdown('**Покупатели товара**')
                buyer_query=st.text_input('Найти покупателя',key='price_buyer_search',placeholder='Название контрагента',label_visibility='collapsed')
                filtered=stats[stats.company.fillna('').str.contains(buyer_query,case=False,regex=False)].reset_index(drop=True)
                if filtered.empty:
                    st.info('Покупатели не найдены в выбранном периоде. Измените период, поиск или общие фильтры.')
                else:
                    pages=max(1,(len(filtered)+6)//7)
                    if st.session_state.get('price_buyer_page',1)>pages: st.session_state.price_buyer_page=1
                    page=st.session_state.get('price_buyer_page',1)
                    current=filtered.iloc[(page-1)*7:page*7].reset_index(drop=True)
                    display=current[['company','quantity','revenue','orders','last_purchase','days_since']].rename(columns={'company':'ПОКУПАТЕЛЬ','quantity':'ОБЪЁМ','revenue':'СУММА, ₽','orders':'ОТГРУЗКИ','last_purchase':'ПОСЛЕДНЯЯ ПОКУПКА','days_since':'ДНЕЙ НАЗАД'})
                    key=table_key('pd_buyers',current.client_id,(st.session_state.price_product_id,beginning,ending))
                    st.dataframe(display,hide_index=True,width='stretch',height=min(515,50+44*len(current)),row_height=44,key=key,on_select=lambda table=key,rows=current[['client_id']]:selected_row(table,rows,on_client),selection_mode='single-row',column_config={'ОБЪЁМ':st.column_config.NumberColumn(format='%.2f',width='small'),'СУММА, ₽':st.column_config.NumberColumn(format='%.2f',width='small'),'ОТГРУЗКИ':st.column_config.NumberColumn(width='small'),'ДНЕЙ НАЗАД':st.column_config.NumberColumn(width='small'),'ПОСЛЕДНЯЯ ПОКУПКА':st.column_config.DatetimeColumn(format='DD.MM.YYYY',width='small'),'ПОКУПАТЕЛЬ':st.column_config.TextColumn(width='medium')})
                    footer,pager=st.columns([2,1],vertical_alignment='center')
                    footer.caption(f'Показано {(page-1)*7+1}–{min(page*7,len(filtered))} из {len(filtered)} · по сумме покупок')
                    pager.number_input('Страница покупателей',min_value=1,max_value=pages,key='price_buyer_page',label_visibility='collapsed')
                    with st.expander('Открыть карточку покупателя'):
                        for buyer in current.itertuples():
                            st.button(str(buyer.company)+' →',key=f'price_buyer_{buyer.client_id}',on_click=on_client,args=(buyer.client_id,),width='stretch')
        with st.container(key='product-design-hint'):
            st.markdown('<div class="pd-hint">✦ <b>Следующий шаг:</b> выберите покупателя, чтобы открыть карточку клиента и подготовить следующий контакт.</div>',unsafe_allow_html=True)
