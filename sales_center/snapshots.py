"""Versioned JSON snapshots. No tokens, pickle, or public/global data cache."""
import hashlib
import json
import pandas as pd
from .storage import Store

VERSION=1
SCHEMAS=[{'client_id','company','segment','city'},
         {'product_id','product','category','price','unit_cost'},
         {'order_id','client_id','date','product_id','product','category','quantity','revenue','cost','profit'}]


def source_id(token):
    return hashlib.sha256(('moysklad-snapshot-v1:'+token.strip()).encode()).hexdigest()


class SnapshotError(RuntimeError): pass


def encode(frames,saved_at):
    data=[]
    for index,frame in enumerate(frames):
        if not SCHEMAS[index].issubset(frame.columns): raise SnapshotError('Снимок не соответствует формату данных приложения.')
        data.append({'frame':json.loads(frame.to_json(orient='split',date_format='iso',double_precision=15)),
            'attrs':{key:frame.attrs[key] for key in ['account_id','excluded_internal_shipments','excluded_empty_shipments'] if key in frame.attrs}})
    return {'version':VERSION,'saved_at':float(saved_at),'frames':data}


def decode(payload):
    try:
        if payload['version']!=VERSION or len(payload['frames'])!=3: raise ValueError()
        saved_at=float(payload['saved_at'])
        if not 0<saved_at<float('inf'): raise ValueError()
        frames=[]
        for index,item in enumerate(payload['frames']):
            frame=pd.DataFrame(**item['frame'])
            if not SCHEMAS[index].issubset(frame.columns): raise ValueError()
            for key in ['client_id','product_id']:
                if key in frame: frame[key]=frame[key].astype('int64')
            if 'date' in frame:
                frame['date']=pd.to_datetime(frame['date'],errors='raise')
                if frame.date.isna().any(): raise ValueError()
            for key in ['quantity','revenue','cost','profit','price','unit_cost']:
                if key in frame: frame[key]=pd.to_numeric(frame[key],errors='raise').astype(float)
            frame.attrs.update(item.get('attrs',{}))
            frames.append(frame)
        if not frames[0].attrs.get('account_id'): raise ValueError()
        return tuple(frames),saved_at
    except (ValueError,KeyError,TypeError,OverflowError):
        raise SnapshotError('Сохранённый снимок устарел или повреждён. Требуется новая загрузка из Моего Склада.') from None


class SnapshotCache:
    def __init__(self,path,token,user_id,database_url=None):
        self.store=Store(path,scope=f'snapshot:{user_id}:{source_id(token)}',database_url=database_url)
        self.persistent=self.store.persistent
    def save(self,frames,saved_at): self.store.put('snapshot','latest',encode(frames,saved_at))
    def load(self):
        try: payload=self.store.get('snapshot','latest')
        except (ValueError,TypeError): raise SnapshotError('Не удалось прочитать сохранённый снимок.') from None
        return decode(payload) if payload is not None else None
