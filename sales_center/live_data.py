"""Strict normalization of posted RUB shipments. Demo data never fills live gaps."""
import hashlib
import math
from urllib.parse import urlsplit
import pandas as pd
from .moysklad import MoySkladError
from .activity_api import ClientActivityClient as MoySkladClient


def external_id(row):
    return row.get('id') or urlsplit(row.get('meta',{}).get('href','')).path.rstrip('/').split('/')[-1]

def local_id(value):
    if not value:
        raise MoySkladError('В данных отсутствует обязательный идентификатор.')
    return int(hashlib.sha256(value.encode()).hexdigest()[:15],16)

def number(obj,key,optional=False):
    value=obj.get(key)
    if value is None and optional: return 0.0
    try:
        value=float(value)
        if not math.isfinite(value): raise ValueError()
        return value
    except (TypeError,ValueError,OverflowError):
        raise MoySkladError(f'В документе поле «{key}» отсутствует или не является конечным числом. Проверьте документ в Моём Складе.') from None

def normalize(counterparties,assortment,documents,currencies,positions):
    try:
        return _normalize(counterparties,assortment,documents,currencies,positions)
    except KeyError as exc:
        raise MoySkladError(f'В ответе API отсутствует обязательное поле: {exc.args[0]}. Обновите загрузку; документ нужно проверить в Моём Складе.') from None
    except (TypeError,ValueError,OverflowError) as exc:
        raise MoySkladError(f'Не удалось преобразовать дату или число в данных отгрузки ({type(exc).__name__}). Проверьте формат документов.') from None

def _normalize(counterparties,assortment,documents,currencies,positions):
    cp = {external_id(c): c for c in counterparties}
    prods = {external_id(p): p for p in assortment}
    currency = {external_id(c): c for c in currencies}
    rows = []
    excluded_internal = 0
    excluded_empty = 0
    for doc in documents:
        if not doc.get('applicable'):
            continue
        if doc.get('agent',{}).get('meta',{}).get('type') == 'organization':
            excluded_internal += 1
            continue
        cid = external_id(doc.get('agent',{}))
        if cid not in cp:
            raise MoySkladError('Контрагент отгрузки недоступен. Проверьте права чтения.')
        cur = currency.get(external_id(doc.get('rate',{}).get('currency',{})),{})
        if str(cur.get('isoCode')).upper() not in {'643', 'RUB'}:
            raise MoySkladError('MVP поддерживает только отгрузки в RUB. Обнаружена другая или неизвестная валюта.')
        moment=pd.Timestamp(doc.get('moment'))
        if pd.isna(moment): raise MoySkladError('В отгрузке отсутствует корректная дата moment.')
        doc_rows = []
        gross_total = 0.0
        for p in positions[doc['id']]:
            product = p.get('assortment') or {}
            pid = external_id(product)
            if not product.get('name'):
                product = prods.get(pid,{})
            qty = number(p,'quantity')
            if qty < 0:
                raise MoySkladError('Отрицательное количество в отгрузке не поддерживается.')
            price = number(p,'price')/100
            base = price*qty*(1-number(p,'discount',optional=True)/100)
            vat = number(p,'vat',optional=True)/100 if doc.get('vatEnabled') else 0
            net = base/(1+vat) if doc.get('vatIncluded') and vat else base
            gross = net*(1+vat)
            gross_total += gross
            # API fields=stock supplies historical unit cost in minor RUB units.
            raw_cost = (p.get('stock') or {}).get('cost')
            cost = number({'cost':raw_cost},'cost')/100*qty if raw_cost is not None else float('nan')
            doc_rows.append(dict(order_id=doc['id'],client_id=local_id(cid),date=moment.normalize(),
                product_id=local_id(pid),product=product.get('name','Товар без названия'),
                category=product.get('pathName') or 'Без категории',quantity=qty,
                revenue=round(net,2),cost=round(cost,2),profit=round(net-cost,2)))
        if not math.isclose(gross_total,number(doc,'sum')/100,abs_tol=max(.02,len(doc_rows)*.01)):
            raise MoySkladError('Сумма позиций не совпадает с суммой отгрузки. Требуется проверка скидок и НДС; данные не загружены.')
        if not doc_rows:
            excluded_empty += 1
        rows.extend(doc_rows)
    clients = pd.DataFrame([dict(client_id=local_id(cid),company=c.get('name','Без названия'),
                                segment='Не указан',city=c.get('actualAddress') or 'Не указан') for cid,c in cp.items()],
                           columns=['client_id','company','segment','city'])
    products = normalize_catalog(assortment,currencies)
    lines = pd.DataFrame(rows,columns=['order_id','client_id','date','product_id','product','category','quantity','revenue','cost','profit'])
    lines['date'] = pd.to_datetime(lines['date'])
    clients.attrs['account_id'] = next((c.get('accountId') for c in counterparties if c.get('accountId')),None)
    clients['phone'] = [c.get('phone') or '' for c in cp.values()]
    clients['email'] = [c.get('email') or '' for c in cp.values()]
    lines.attrs['excluded_internal_shipments'] = excluded_internal
    lines.attrs['excluded_empty_shipments'] = excluded_empty
    if clients.client_id.duplicated().any() or products.product_id.duplicated().any():
        raise MoySkladError('Обнаружено совпадение внутренних идентификаторов. Загрузка остановлена.')
    return clients,products,lines

def normalize_catalog(assortment, currencies):
    from .price_catalog import normalize_catalog as normalize_prices
    return normalize_prices(assortment, currencies)


def load_catalog(token):
    from .price_catalog import load_catalog as load_prices
    return load_prices(token)


def load_live(today, token=None, progress=None):
    api = MoySkladClient(token=token)
    def report(stage, count=0, total=0):
        if progress:
            progress(stage, count, total)
    def collect(entity, label, params=None):
        report(label)
        result=api.list_entities(entity,params,progress=lambda count,total: report(label,count,total))
        if any(not isinstance(row,dict) for row in result):
            raise MoySkladError(f'{label}: API вернул строку неизвестного формата.')
        return result
    try:
        # Verify credentials before starting an expensive shipment read.
        currencies = collect('currency','Проверка подключения и валют')
        start = pd.Timestamp(today)-pd.DateOffset(months=12)
        end = pd.Timestamp(today)+pd.Timedelta(days=1)
        docs = collect('demand','Загрузка отгрузок',{
            'filter':f'applicable=true;moment>={start:%Y-%m-%d} 00:00:00;moment<{end:%Y-%m-%d} 00:00:00',
            'expand':'positions.assortment','fields':'stock'})
        if len({doc['id'] for doc in docs}) != len(docs):
            raise MoySkladError('Отгрузки изменились во время загрузки. Повторите подключение.')
        positions = {}
        for index,doc in enumerate(docs):
            embedded = doc.get('positions',{})
            rows = embedded.get('rows')
            if rows is not None and len(rows) == embedded.get('meta',{}).get('size',len(rows)):
                positions[doc['id']] = rows
            else:
                report('Загрузка дополнительных позиций',index+1,len(docs))
                positions[doc['id']] = api.demand_positions(doc['id'])
        cp = collect('counterparty','Загрузка контрагентов')
        client_ids = {external_id(c) for c in cp}
        if any(external_id(d.get('agent',{})) not in client_ids and d.get('agent',{}).get('meta',{}).get('type') != 'organization' for d in docs):
            archived = collect('counterparty','Загрузка архивных контрагентов',{'filter':'archived=true'})
            merged = {external_id(c):c for c in cp}
            merged.update({external_id(c):c for c in archived})
            cp = list(merged.values())
        products = collect('assortment','Загрузка товаров и прайс-листа',{'expand':'uom'})
        report('Проверка и обработка данных')
        frames=normalize(cp,products,docs,currencies,positions)
        from .client_segments import enrich
        employees=collect('employee','Загрузка владельцев-сотрудников')
        history=collect('demand','Загрузка всей истории покупок',{'filter':'applicable=true'})
        currency_by_id={external_id(c):c for c in currencies}
        for doc in history:
            if doc.get('agent',{}).get('meta',{}).get('type')=='organization': continue
            cur=currency_by_id.get(external_id(doc.get('rate',{}).get('currency',{})),{})
            if str(cur.get('isoCode')).upper() not in {'643','RUB'}:
                raise MoySkladError('История содержит другую или неизвестную валюту. Суммы не смешиваются.')
        recent_orders=collect('customerorder','Загрузка новых заказов покупателей',{'filter':f'created>={(pd.Timestamp(today)-pd.Timedelta(days=10)):%Y-%m-%d} 00:00:00'})
        # Resolve archived counterparties referenced by the full history as well.
        known={external_id(c) for c in cp}
        if any(external_id(d.get('agent') or {}) not in known and d.get('agent',{}).get('meta',{}).get('type')!='organization' for d in history):
            archived=collect('counterparty','Загрузка архивных контрагентов истории',{'filter':'archived=true'})
            cp=list({external_id(c):c for c in cp+archived}.values())
            frames=normalize(cp,products,docs,currencies,positions)
        return enrich(frames[0],cp,employees,history,recent_orders,today),frames[1],frames[2]
    except (KeyError,TypeError,ValueError,OverflowError) as exc:
        field=f' Поле: {exc.args[0]}.' if isinstance(exc,KeyError) else ''
        raise MoySkladError(f'Неверный формат коллекции API ({type(exc).__name__}).{field} Частичная загрузка отменена; прежние данные сохранены.') from None
    finally:
        api.session.close()
