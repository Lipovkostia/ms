"""Strict normalization of posted RUB shipments. Demo data never fills live gaps."""
import hashlib
import math
from urllib.parse import urlsplit
import pandas as pd
from .moysklad import MoySkladClient, MoySkladError


def external_id(row):
    return row.get('id') or urlsplit(row.get('meta',{}).get('href','')).path.rstrip('/').split('/')[-1]

def local_id(value):
    if not value:
        raise MoySkladError('В данных отсутствует обязательный идентификатор.')
    return int(hashlib.sha256(value.encode()).hexdigest()[:15],16)

def normalize(counterparties,assortment,documents,currencies,positions):
    cp = {external_id(c): c for c in counterparties}
    prods = {external_id(p): p for p in assortment}
    currency = {external_id(c): c for c in currencies}
    rows = []
    for doc in documents:
        if not doc.get('applicable'):
            continue
        cid = external_id(doc.get('agent',{}))
        if cid not in cp:
            raise MoySkladError('Контрагент отгрузки недоступен. Проверьте права чтения.')
        cur = currency.get(external_id(doc.get('rate',{}).get('currency',{})),{})
        if str(cur.get('isoCode')) != '643':
            raise MoySkladError('MVP поддерживает только отгрузки в RUB. Обнаружена другая или неизвестная валюта.')
        doc_rows = []
        gross_total = 0.0
        for p in positions[doc['id']]:
            product = p.get('assortment',{})
            pid = external_id(product)
            if not product.get('name'):
                product = prods.get(pid,{})
            qty = float(p['quantity'])
            if qty < 0:
                raise MoySkladError('Отрицательное количество в отгрузке не поддерживается.')
            price = float(p['price'])/100
            base = price*qty*(1-float(p.get('discount',0))/100)
            vat = float(p.get('vat',0))/100 if doc.get('vatEnabled') else 0
            net = base/(1+vat) if doc.get('vatIncluded') and vat else base
            gross = net*(1+vat)
            gross_total += gross
            # API fields=stock supplies historical unit cost in minor RUB units.
            raw_cost = p.get('stock',{}).get('cost')
            cost = float(raw_cost)/100*qty if raw_cost is not None else float('nan')
            doc_rows.append(dict(order_id=doc['id'],client_id=local_id(cid),date=pd.Timestamp(doc['moment']).normalize(),
                product_id=local_id(pid),product=product.get('name','Товар без названия'),
                category=product.get('pathName') or 'Без категории',quantity=qty,
                revenue=round(net,2),cost=round(cost,2),profit=round(net-cost,2)))
        if not math.isclose(gross_total,float(doc['sum'])/100,abs_tol=max(.02,len(doc_rows)*.01)):
            raise MoySkladError('Сумма позиций не совпадает с суммой отгрузки. Требуется проверка скидок и НДС; данные не загружены.')
        rows.extend(doc_rows)
    clients = pd.DataFrame([dict(client_id=local_id(cid),company=c.get('name','Без названия'),
                                segment='Не указан',city=c.get('actualAddress') or 'Не указан') for cid,c in cp.items()],
                           columns=['client_id','company','segment','city'])
    products = pd.DataFrame([dict(product_id=local_id(pid),product=p.get('name','Без названия'),
                                   category=p.get('pathName') or 'Без категории',price=float('nan'),unit_cost=float('nan')) for pid,p in prods.items()],
                            columns=['product_id','product','category','price','unit_cost'])
    lines = pd.DataFrame(rows,columns=['order_id','client_id','date','product_id','product','category','quantity','revenue','cost','profit'])
    lines['date'] = pd.to_datetime(lines['date'])
    if clients.client_id.duplicated().any() or products.product_id.duplicated().any():
        raise MoySkladError('Обнаружено совпадение внутренних идентификаторов. Загрузка остановлена.')
    return clients,products,lines

def load_live(today, token=None):
    api = MoySkladClient(token=token)
    start = pd.Timestamp(today)-pd.DateOffset(months=12)
    end = pd.Timestamp(today)+pd.Timedelta(days=1)
    docs = api.list_entities('demand',{'filter':f'applicable=true;moment>={start:%Y-%m-%d} 00:00:00;moment<{end:%Y-%m-%d} 00:00:00'})
    positions = {doc['id']:api.demand_positions(doc['id']) for doc in docs}
    return normalize(api.list_entities('counterparty'),api.list_entities('assortment'),docs,
                     api.list_entities('currency'),positions)
