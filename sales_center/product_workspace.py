"""Three-column current price list → product buyers → customer workflow."""
import streamlit as st
import pandas as pd
from .product_analytics import price_types,price_list,category_paths,buyers
from .presentation import money
from .analytics import period


def select_product(pid):
    st.session_state.price_product_id=int(pid)
    st.session_state.price_buyer_page=1


def render(products,clients,lines,today,start,end,on_client,on_catalog_refresh):
    types=price_types(products)
    if not types:
        st.info('В этом снимке нет типов цен. Загрузите текущий каталог из Моего Склада — история заказов останется на месте.')
        if st.button('Загрузить текущий прайс-лист',key='load_price_catalog'): on_catalog_refresh()
        return
    preferred=next((key for key,name in types.items() if name=='Цена опт безнал'),next(iter(types)))
    if st.button('Обновить прайс-лист',key='refresh_price_catalog'): on_catalog_refresh()
    price_type=st.selectbox('Тип цен прайс-листа',list(types),index=list(types).index(preferred),format_func=lambda key:types[key],key='price_type')
    positive=st.checkbox('Только товары с ненулевой ценой',value=True,key='positive_prices')
    st.caption('Действующие товары и группы Моего Склада, выбранный тип цен. Текущий прайс не подтверждает наличие на складе. История покупателей по умолчанию — все загруженные 12 месяцев.')
    catalog=price_list(products,price_type,positive)
    if catalog.empty:
        st.info('В выбранном типе цен нет подходящих товаров. Измените тип цен или отключите фильтр ненулевых цен.')
        return
    with st.container(key='product-workspace'):
        groups_col,items_col,buyers_col=st.columns([1,1.5,1.8],gap='medium')
        with groups_col,st.container(border=True):
            st.subheader('Категории прайс-листа')
            categories=['Все категории']+category_paths(catalog)
            if st.session_state.get('price_category') not in categories: st.session_state.price_category=categories[0]
            category=st.radio('Категория товара',categories,format_func=lambda p:'Все категории' if p=='Все категории' else '　'*(p.count('/'))+p.split('/')[-1],key='price_category')
        with items_col,st.container(border=True):
            st.subheader('Товары')
            query=st.text_input('Найти товар в прайс-листе',placeholder='Название, код или артикул',key='price_search')
            view=catalog
            if category!='Все категории': view=view[view.category.eq(category)|view.category.str.startswith(category+'/')]
            match=view['product'].str.contains(query,case=False,regex=False)
            for column in ['code','article']:
                if column in view: match=match|view[column].fillna('').str.contains(query,case=False,regex=False)
            view=view[match].sort_values(['category','product','product_id'])
            st.caption(f'Товаров: {len(view):,} · {types[price_type]}')
            if view.empty: st.info('Товары не найдены.'); return
            ids=view.product_id.tolist()
            if st.session_state.get('price_product_id') not in ids: select_product(ids[0])
            selected_id=st.session_state.price_product_id
            count=max(1,(len(view)+14)//15)
            if st.session_state.get('price_product_page',1)>count: st.session_state.price_product_page=1
            page=st.number_input('Страница товаров',min_value=1,max_value=count,value=1,key='price_product_page')
            for row in view.iloc[(page-1)*15:page*15].itertuples():
                suffix='₽' if row.currency=='RUB' else row.currency
                st.button(f'{row.product} · {row.list_price:,.2f} {suffix}',key=f'price_item_{row.product_id}',type='primary' if row.product_id==selected_id else 'secondary',width='stretch',on_click=select_product,args=(row.product_id,))
                st.caption(row.category+' · '+str(getattr(row,'code','')))
        product=view.set_index('product_id').loc[selected_id]
        with buyers_col,st.container(border=True):
            st.subheader('Покупатели товара')
            st.text(product['product'])
            st.caption(product.category+' · количество в '+str(product.get('unit','ед. товара')))
            selected_history=st.radio('История покупателей',['Все 12 месяцев','Выбранный период'],horizontal=True,key='buyer_history')
            history=lines if selected_history=='Все 12 месяцев' else period(lines,start,end)
            stats=buyers(history,clients,selected_id,today)
            if stats.empty: st.info('В доступной истории этот товар ещё не покупали.'); return
            a,b=st.columns(2)
            a.metric('Покупателей',len(stats))
            b.metric('Сумма покупок',money(stats.revenue.sum()))
            st.caption('Суммы фактических отгрузок без НДС; возвраты не вычитаются. Количество не пересчитывается между единицами измерения.')
            customer_query=st.text_input('Найти покупателя',key='price_buyer_search')
            stats=stats[stats.company.fillna('').str.contains(customer_query,case=False,regex=False)]
            st.dataframe(stats[['company','quantity','revenue','orders','last_purchase','days_since']].rename(columns={'company':'Контрагент','quantity':'Объём','revenue':'Сумма, ₽','orders':'Заказов','last_purchase':'Последняя покупка','days_since':'Дней назад'}),hide_index=True,width='stretch',height=300)
            pages=max(1,(len(stats)+9)//10)
            if st.session_state.get('price_buyer_page',1)>pages: st.session_state.price_buyer_page=1
            page=st.number_input('Страница покупателей',min_value=1,max_value=pages,value=1,key='price_buyer_page')
            for buyer in stats.iloc[(page-1)*10:page*10].itertuples():
                st.button('Открыть клиента — '+str(buyer.company),key=f'price_buyer_{buyer.client_id}',on_click=on_client,args=(buyer.client_id,),width='stretch')
                st.caption(f'{buyer.quantity:g} {product.get("unit","ед. товара")} · {money(buyer.revenue)} · {buyer.days_since} дн. назад')
