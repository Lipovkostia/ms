"""Explicit read-only connection checks and user-requested AI drafts."""
import requests
import re

class ProviderError(RuntimeError): pass

def request(method,url,headers=None,payload=None):
    try:
        r=requests.request(method,url,headers=headers,json=payload,timeout=(10,60),allow_redirects=False)
        if not r.ok or 300 <= r.status_code < 400:
            raise ProviderError(f'Сервис отклонил запрос (HTTP {r.status_code}). Проверьте ключ, права и баланс.')
        value=r.json()
        if not isinstance(value,dict): raise ProviderError('Сервис вернул неизвестный формат ответа.')
        return value
    except (requests.RequestException,ValueError):
        # Vendor URLs may contain tokens. Never expose exception text.
        raise ProviderError('Сервис не ответил корректно. Проверьте подключение.') from None

class GreenAPI:
    def __init__(self,instance,token):
        if not re.fullmatch(r'\d+',instance or '') or not re.fullmatch(r'[A-Za-z0-9_-]+',token or ''):
            raise ProviderError('Укажите ID инстанса и токен Green API.')
        self.base=f'https://api.green-api.com/waInstance{instance}'
        self.token=token
    def state(self):
        r=request('GET',f'{self.base}/getStateInstance/{self.token}')
        if not r.get('stateInstance'): raise ProviderError('Green API вернул неизвестный формат ответа.')
        return r['stateInstance']

class Telegram:
    def __init__(self,token):
        if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+',token or ''): raise ProviderError('Укажите токен Telegram-бота.')
        self.token=token
    def state(self):
        r=request('GET',f'https://api.telegram.org/bot{self.token}/getMe')
        if not r.get('ok'): raise ProviderError('Telegram отклонил токен бота.')
        return r['result'].get('username','Бот')

class OpenRouter:
    BASE='https://openrouter.ai/api/v1'
    def __init__(self,key):
        if not key: raise ProviderError('Введите ключ OpenRouter.')
        self.headers={'Authorization':f'Bearer {key}'}
    def models(self):
        r=request('GET',self.BASE+'/models',self.headers)
        return sorted([{'id':m['id'],'name':m.get('name',m['id'])} for m in r.get('data',[])],key=lambda m:m['name'])
    def check(self):
        request('GET',self.BASE+'/auth/key',self.headers)
        return self.models()
    def draft(self,model,facts):
        r=request('POST',self.BASE+'/chat/completions',self.headers,{
            'model':model,'messages':[
                {'role':'system','content':'Ты помощник менеджера оптовых продаж. Пиши по-русски. Используй только переданные факты. Не придумывай наличие, цены, результаты и гарантии. Дай краткую рекомендацию и черновик сообщения. Не пересчитывай финансовые показатели; они уже рассчитаны Python. Никаких действий или отправки сообщений.'},
                {'role':'user','content':str(facts)}], 'max_tokens':700})
        try: return r['choices'][0]['message']['content']
        except (KeyError,IndexError,TypeError): raise ProviderError('Модель не вернула текст ответа.') from None

class MAX:
    def __init__(self,token):
        if not token: raise ProviderError('Введите токен MAX-бота.')
        self.token=token
    def state(self):
        r=request('GET','https://platform-api2.max.ru/me',{'Authorization':self.token})
        if not r.get('user_id'): raise ProviderError('MAX не вернул данные бота.')
        return r.get('name') or str(r['user_id'])
