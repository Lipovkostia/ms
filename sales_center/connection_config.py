"""Persistent credentials come from hosting secrets, never application records."""
from dataclasses import dataclass,field
import os


def enabled(value):
    return value is True or isinstance(value,str) and value.strip().lower() in {'true','1','yes'}

@dataclass(frozen=True)
class ConnectionConfig:
    token:str=field(default='',repr=False)
    database_url:str|None=field(default=None,repr=False)
    authorized:bool=False
    auto_connect:bool=True
    interval:int=30

    @property
    def automatic(self): return bool(self.token and self.authorized and self.auto_connect)


def read_config(secrets,user_id,environ=None):
    env=os.environ if environ is None else environ
    def get(key,default=None):
        value=secrets.get(key)
        return value if value is not None else env.get(key,default)
    token=str(get('MOYSKLAD_TOKEN','') or '').strip()
    try: interval=int(get('MOYSKLAD_SYNC_MINUTES',30))
    except (TypeError,ValueError): interval=30
    if interval not in {0,15,30,60}: interval=30
    return ConnectionConfig(token=token,database_url=get('DATABASE_URL'),
        authorized=user_id!='personal' or enabled(get('MOYSKLAD_PRIVATE_DEPLOYMENT',False)),
        auto_connect=enabled(get('MOYSKLAD_AUTO_CONNECT',True)),interval=interval)
