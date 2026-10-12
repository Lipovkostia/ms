"""Auditable shared filters for the product catalogue, buyers and CSV export.

Only the history already loaded by the application is available here. Quantities
remain in each product's native unit; this module never totals unlike units.
"""
import pandas as pd

from .product_analytics import price_list, price_types, category_paths, buyers


PERIODS = {
    '30': '30 дней',
    '90': '90 дней',
    '12m': '12 месяцев',
    'all': 'Весь доступный период',
}


def period_window(lines, today, key):
    """Return inclusive dates, clipped to available history, never future rows."""
    end = pd.Timestamp(today).normalize()
    if key == '30':
        start = end - pd.Timedelta(days=29)
    elif key == '90':
        start = end - pd.Timedelta(days=89)
    elif key == '12m':
        start = end - pd.DateOffset(months=12) + pd.Timedelta(days=1)
    elif key == 'all':
        start = end
    else:
        raise ValueError('Неизвестный период товарной аналитики.')
    if not lines.empty:
        dates = pd.to_datetime(lines['date']).dropna()
        dates = dates[dates < end + pd.Timedelta(days=1)]
        if not dates.empty:
            earliest = dates.min().normalize()
            start = earliest if key == 'all' else max(start, earliest)
    return start, end


def warehouse_options(lines):
    """Offer warehouses only if actual shipment data contains their names.

    With warehouse_id+warehouse the mapping keys are IDs. With warehouse alone
    the names are both keys and labels. No warehouse is inferred from products.
    """
    if 'warehouse' not in lines:
        return {}
    available = lines.loc[lines['warehouse'].notna()].copy()
    available = available[available['warehouse'].astype(str).str.strip().ne('')]
    if 'warehouse_id' in available:
        available = available[available['warehouse_id'].notna()]
        pairs = available[['warehouse_id', 'warehouse']].drop_duplicates('warehouse_id')
        return dict(sorted(pairs.itertuples(index=False, name=None), key=lambda pair: str(pair[1])))
    names = sorted(set(available['warehouse'].astype(str)))
    return dict(zip(names, names))


def filter_sales(lines, start, end, buyer_id=None, warehouse_id=None):
    """Positive shipment quantities in the same period used by both panels."""
    dates = pd.to_datetime(lines['date'])
    mask = (dates >= pd.Timestamp(start)) & (dates < pd.Timestamp(end) + pd.Timedelta(days=1))
    mask &= lines['quantity'] > 0
    if buyer_id is not None:
        mask &= lines['client_id'].eq(buyer_id)
    if warehouse_id is not None:
        options = warehouse_options(lines)
        if warehouse_id not in options:
            raise ValueError('В загруженной истории нет выбранного склада.')
        column = 'warehouse_id' if 'warehouse_id' in lines else 'warehouse'
        mask &= lines[column].eq(warehouse_id)
    return lines.loc[mask].copy()


def catalog_view(products, sales, price_type, category=None, query='', only_sales=False,
                 sort='revenue', positive=True):
    """Join real current prices to filtered shipment totals by exact product ID.

    Sale prices are catalogue prices, not realised revenue. sold_revenue comes
    only from existing normalised shipment lines (VAT/discount rules preserved).
    """
    view = price_list(products, price_type, positive)
    if category is not None:
        paths = view['category'].fillna('').astype(str)
        view = view[paths.eq(category) | paths.str.startswith(str(category) + '/')]
    query = str(query or '').strip()
    if query:
        matched = pd.Series(False, index=view.index)
        for column in ['product', 'code', 'article']:
            if column in view:
                matched |= view[column].fillna('').astype(str).str.contains(query, case=False, regex=False)
        view = view.loc[matched]
    positive_sales = sales.loc[sales['quantity'] > 0]
    totals = positive_sales.groupby('product_id', as_index=False).agg(
        sold_quantity=('quantity', 'sum'), sold_revenue=('revenue', 'sum'),
        sold_orders=('order_id', 'nunique'), sold_buyers=('client_id', 'nunique'),
    )
    view = view.merge(totals, on='product_id', how='left')
    view[['sold_quantity', 'sold_revenue']] = view[['sold_quantity', 'sold_revenue']].fillna(0)
    view[['sold_orders', 'sold_buyers']] = view[['sold_orders', 'sold_buyers']].fillna(0).astype(int)
    if only_sales:
        view = view[view['sold_quantity'] > 0]
    sorts = {'revenue': ('sold_revenue', False), 'name': ('product', True),
             'price': ('list_price', False), 'quantity': ('sold_quantity', False)}
    if sort not in sorts:
        raise ValueError('Неизвестная сортировка товаров.')
    column, ascending = sorts[sort]
    columns = [column] + ([] if column == 'product' else ['product']) + ['product_id']
    direction = [ascending] + ([] if column == 'product' else [True]) + [True]
    return view.sort_values(columns, ascending=direction, kind='stable').reset_index(drop=True)


def export_catalog_csv(view):
    """Export exactly the filtered, sorted view, with explicit native units.

    UTF-8 BOM supports Russian names in spreadsheet tools. Text beginning with
    spreadsheet formula markers is escaped, without changing numeric values.
    """
    columns = {
        'product_id': 'ID товара', 'product': 'Товар', 'code': 'Код',
        'article': 'Артикул', 'category': 'Категория', 'list_price': 'Цена прайс-листа',
        'currency': 'Валюта цены', 'unit': 'Единица измерения',
        'sold_quantity': 'Продано в единицах товара', 'sold_revenue': 'Выручка без НДС, ₽',
        'sold_orders': 'Количество отгрузок', 'sold_buyers': 'Количество покупателей',
    }
    exported = view[[column for column in columns if column in view]].copy()
    for column in ['product', 'code', 'article', 'category', 'currency', 'unit']:
        if column in exported:
            exported[column] = exported[column].map(
                lambda value: "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value)
    return exported.rename(columns=columns).to_csv(index=False).encode('utf-8-sig')
