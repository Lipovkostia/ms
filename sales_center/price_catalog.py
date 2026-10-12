"""Real price catalogue loader, separately imported across Streamlit updates."""
import pandas as pd
from .moysklad import MoySkladClient, MoySkladError
from .live_data import external_id, local_id, number


def normalize_catalog(assortment,currencies):
    currency={external_id(c):c for c in currencies}
    rows=[]
    for p in assortment:
        entries=[]
        for price in p.get('salePrices') or []:
            kind=price.get('priceType') or {}
            pid=external_id(kind)
            value=price.get('value')
            if not pid or value is None: continue
            value=number({'value':value},'value')/100
            if value<0: raise MoySkladError('В каталоге получена отрицательная цена.')
            cur=currency.get(external_id(price.get('currency') or {}),{})
            code=str(cur.get('isoCode') or cur.get('name') or 'Неизвестная валюта')
            entries.append({'id':pid,'name':kind.get('name') or 'Тип цены без названия','value':value,'currency':'RUB' if code.upper() in {'643','RUB'} else code})
        rows.append(dict(product_id=local_id(external_id(p)),product=p.get('name') or 'Без названия',
            category=p.get('pathName') or 'Без категории',price=float('nan'),unit_cost=float('nan'),
            archived=bool(p.get('archived',False)),entity_type=p.get('meta',{}).get('type','product'),
            code=p.get('code') or '',article=p.get('article') or '',unit=(p.get('uom') or {}).get('name') or 'ед. товара',sale_prices=entries))
    result=pd.DataFrame(rows,columns=['product_id','product','category','price','unit_cost','archived','entity_type','code','article','unit','sale_prices'])
    if result.product_id.duplicated().any(): raise MoySkladError('Каталог содержит повторные идентификаторы. Обновление отменено.')
    return result


def load_catalog(token):
    api=MoySkladClient(token=token)
    try:
        return normalize_catalog(api.list_entities('assortment',{'expand':'uom'}),api.list_entities('currency'))
    finally: api.session.close()


