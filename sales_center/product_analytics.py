"""Current price selection and exact product-ID buyer aggregation."""
import pandas as pd


def price_types(products):
    found={}
    if 'sale_prices' not in products: return found
    for entries in products.sale_prices:
        for entry in entries if isinstance(entries,list) else []:
            found[entry['id']]=entry['name']
    return dict(sorted(found.items(),key=lambda item:item[1]))


def price_list(products,price_type,positive=True):
    rows=[]
    for product in products.to_dict('records'):
        if product.get('archived',False) or product.get('entity_type','product') not in ['product','variant','bundle']: continue
        for entry in product.get('sale_prices',[]) or []:
            if entry['id']!=price_type or positive and entry['value']<=0: continue
            rows.append({**product,'list_price':entry['value'],'currency':entry['currency']})
            break
    return pd.DataFrame(rows,columns=list(products.columns)+['list_price','currency'])


def category_paths(frame):
    result=set()
    for path in frame.category:
        parts=path.split('/')
        result.update('/'.join(parts[:index]) for index in range(1,len(parts)+1))
    return sorted(result)


def buyers(lines,clients,product_id,today):
    own=lines[(lines.product_id==product_id)&(lines.quantity>0)]
    frame=own.groupby('client_id',as_index=False).agg(quantity=('quantity','sum'),revenue=('revenue','sum'),orders=('order_id','nunique'),last_purchase=('date','max'))
    frame['days_since']=(pd.Timestamp(today).normalize()-frame.last_purchase.dt.normalize()).dt.days
    return frame.merge(clients[['client_id','company']],on='client_id',how='left').sort_values(['revenue','company'],ascending=[False,True])
