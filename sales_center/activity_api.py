"""Activity reads remain compatible with the API module cached by Streamlit.

The allowlist belongs to this adapter, not to a previously loaded base class.
Transport, credential handling and exception identity are inherited unchanged.
"""
import pandas as pd
from .moysklad import MoySkladClient, MoySkladError


class ClientActivityClient(MoySkladClient):
    ENTITIES=frozenset({'counterparty','assortment','demand','currency','employee','customerorder'})


def register_activity_entities():
    """Bridge existing loader references without replacing classes or exceptions.

    Old live_data/sync functions can retain the base class after a deployment.
    Replace only its fixed endpoint allowlist; requests still use the same TLS,
    authentication, pagination, retries and HTTP error handling.
    """
    MoySkladClient.ENTITIES=ClientActivityClient.ENTITIES


register_activity_entities()


def load_client_activity(token,clients,today):
    """Upgrade older saved snapshots without rereading shipment positions."""
    from .client_segments import enrich
    from .live_data import external_id
    api=ClientActivityClient(token)
    try:
        cp=api.list_entities('counterparty')
        archived=api.list_entities('counterparty',{'filter':'archived=true'})
        cp=list({external_id(c):c for c in cp+archived}.values())
        employees=api.list_entities('employee')
        currencies={external_id(c):c for c in api.list_entities('currency')}
        history=api.list_entities('demand',{'filter':'applicable=true'})
        for doc in history:
            if doc.get('agent',{}).get('meta',{}).get('type')=='organization': continue
            currency=currencies.get(external_id(doc.get('rate',{}).get('currency',{})),{})
            if str(currency.get('isoCode')).upper() not in {'643','RUB'}:
                raise MoySkladError('История содержит другую или неизвестную валюту. Суммы не смешиваются.')
        new=api.list_entities('customerorder',{'filter':f'created>={(pd.Timestamp(today)-pd.Timedelta(days=10)):%Y-%m-%d} 00:00:00'})
        return enrich(clients,cp,employees,history,new,today)
    except (KeyError,TypeError,ValueError,OverflowError):
        raise MoySkladError('Мой Склад вернул некорректные данные истории клиентов. Загрузка отменена; прежние данные сохранены.') from None
    finally: api.session.close()
