"""Deterministic synthetic orders; no external company data."""
from datetime import date
import numpy as np
import pandas as pd

CATEGORIES = ['Хамон', 'Сыры', 'Оливки', 'Оливковое масло', 'Деликатесы']

def demo_data(today=None):
    today = pd.Timestamp(today or date.today()).normalize()
    rng = np.random.default_rng(42)
    products = pd.DataFrame([
        (1, 'Хамон Серрано, кг', 'Хамон', 2400, 1650),
        (2, 'Хамон Иберико, кг', 'Хамон', 6900, 4900),
        (3, 'Манчего, кг', 'Сыры', 2300, 1550),
        (4, 'Пармезан, кг', 'Сыры', 2100, 1400),
        (5, 'Бри, кг', 'Сыры', 1800, 1200),
        (6, 'Оливки Каламата, банка', 'Оливки', 650, 410),
        (7, 'Оливки с косточкой, банка', 'Оливки', 480, 300),
        (8, 'Оливковое масло Extra Virgin, л', 'Оливковое масло', 1250, 850),
        (9, 'Трюфельная паста, банка', 'Деликатесы', 950, 620),
        (10, 'Вяленые томаты, банка', 'Деликатесы', 720, 450),
        (11, 'Артишоки, банка', 'Деликатесы', 680, 420),
        (12, 'Бальзамический уксус, л', 'Деликатесы', 1100, 720),
    ], columns=['product_id', 'product', 'category', 'price', 'unit_cost'])
    products['archived']=False
    products['entity_type']='product'
    products['code']=['TEST-'+str(pid) for pid in products.product_id]
    products['article']=''
    products['unit']='ед. товара'
    products['sale_prices']=[[{'id':'wholesale','name':'Цена опт безнал','value':float(price),'currency':'RUB'}] for price in products.price]
    names = ['Гастро', 'Вкус', 'Олива', 'Прованс', 'Деликат', 'Терра', 'Лавка', 'Сырный дом', 'Палитра', 'Премиум']
    segments = ['Ресторан', 'Магазин', 'Оптовик', 'Отель', 'Кейтеринг']
    cities = ['Москва', 'Санкт-Петербург', 'Казань', 'Сочи', 'Екатеринбург']
    clients, lines = [], []
    start = today - pd.DateOffset(months=12)
    order_id = 0
    for cid in range(1, 101):
        segment = segments[(cid-1) % 5]
        clients.append((cid, f'ООО «{names[(cid-1)%10]} {cid:03}»', segment, cities[(cid//7)%5]))
        cycle = int(rng.choice([7, 14, 20, 30, 45, 60]))
        stop = today - pd.Timedelta(days=cycle * (2.8 if cid % 7 == 0 else .3))
        d = start + pd.Timedelta(days=int(rng.integers(0, 90)))
        preferred = [1, 2, 3, 4, 5] if cid % 4 == 0 else list(range(1, 13))
        while d <= stop:
            order_id += 1
            picks = rng.choice(preferred, size=min(len(preferred), int(rng.integers(2, 5))), replace=False)
            for pid in picks:
                p = products.loc[products.product_id == pid].iloc[0]
                scale = .55 if cid % 9 == 0 and d > today-pd.Timedelta(days=90) else 1
                scale *= 1.5 if cid % 11 == 0 and d > today-pd.Timedelta(days=90) else 1
                qty = max(1, int(rng.integers(4, 25)*scale))
                revenue = round(float(p.price)*qty, 2)
                cost = round(float(p.unit_cost)*qty, 2)
                lines.append((order_id, cid, d, int(pid), qty, revenue, cost))
            d += pd.Timedelta(days=max(2, cycle+int(rng.integers(-max(1,cycle//4), max(2,cycle//4)))))
    clients = pd.DataFrame(clients, columns=['client_id', 'company', 'segment', 'city'])
    lines = pd.DataFrame(lines, columns=['order_id', 'client_id', 'date', 'product_id', 'quantity', 'revenue', 'cost'])
    lines = lines.merge(products[['product_id', 'product', 'category']], on='product_id')
    lines['profit'] = lines.revenue-lines.cost
    return clients, products, lines
