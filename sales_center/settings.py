"""Connection checks never persist credentials; saved preferences contain model IDs only."""
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError
from .providers import GreenAPI,Telegram,MAX,OpenRouter,ProviderError


def connections():
    st.subheader('Подключения')
    st.caption('Ключи остаются только в памяти вашей браузерной сессии. Не вводите их в чат или GitHub. Проверка подключения не отправляет сообщения.')
    for name,provider in [('WhatsApp · Green API',GreenAPI),('Telegram · Bot API',Telegram),('MAX · Bot API',MAX),('OpenRouter',OpenRouter)]:
        with st.expander(name):
            st.caption('WhatsApp работает через Green API. Telegram и MAX подключаются отдельными официальными Bot API.')
            with st.form('provider_'+provider.__name__,clear_on_submit=True):
                instance=st.text_input('ID инстанса') if provider is GreenAPI else None
                key=st.text_input('Токен / API-ключ',type='password')
                submit=st.form_submit_button('Проверить подключение')
            if submit:
                try:
                    api=provider(instance,key) if provider is GreenAPI else provider(key)
                    result=api.check() if provider is OpenRouter else api.state()
                    if provider is OpenRouter:
                        if not result: raise ProviderError('Список моделей пуст.')
                        st.session_state.provider_models=result
                        st.session_state.provider_openrouter=api
                        result=f'Доступно моделей: {len(result)}'
                    st.session_state['provider_status_'+provider.__name__]=str(result)
                    st.success('Проверка выполнена: '+str(result))
                except ProviderError as exc:
                    st.session_state.pop('provider_status_'+provider.__name__,None)
                    if provider is OpenRouter:
                        st.session_state.pop('provider_openrouter',None)
                        st.session_state.pop('provider_models',None)
                    st.error(str(exc))
            if st.session_state.get('provider_status_'+provider.__name__): st.caption('Последняя проверка: '+st.session_state['provider_status_'+provider.__name__])
    st.subheader('Сотрудники и сохранение')
    st.write('Для отдельных аккаунтов настройте OIDC-вход и список allowed_emails в Streamlit Secrets. У каждого сотрудника будут собственные задачи, заметки, черновики и модель. До настройки входа приложение работает в персональном режиме: общий браузер означает общие записи.')
    st.write('Для постоянного хранения на Streamlit Cloud задайте DATABASE_URL внешнего PostgreSQL. Локальная SQLite подходит для запуска на своём компьютере; облако может удалить её при перезапуске. История Моего Склада хранится только в памяти сессии и загружается заново после её окончания.')
    st.caption('Инструкция и шаблон Secrets находятся в README. Автоматическая отправка и получение сообщений пока не реализованы.')


def model_picker(store,cid,client,recs):
    api=st.session_state.get('provider_openrouter')
    models=st.session_state.get('provider_models',[])
    if not api or not models:
        st.caption('Правила Python работают без AI-ключа. Для AI-черновиков подключите OpenRouter в Настройках.')
        return
    ids=[m['id'] for m in models]
    names={m['id']:m['name'] for m in models}
    saved=store.get('preference','model',ids[0])
    model=st.selectbox('Модель AI',ids,index=ids.index(saved) if saved in ids else 0,format_func=lambda x:names[x],key='model_choice')
    if st.button('Сохранить мою модель'):
        try:
            store.put('preference','model',model)
            st.success('Модель сохранена для вашего аккаунта.')
        except SQLAlchemyError: st.error('Не удалось сохранить выбор модели.')
    consent=st.checkbox('Разрешаю передать имя клиента и агрегаты в выбранную модель',key=f'consent_{cid}')
    st.caption('Запрос может тарифицироваться OpenRouter. Телефон, email и полная история заказов не передаются.')
    if st.button('Подготовить AI-черновик',disabled=not consent):
        facts={'client':client.company,'average':client.average,'frequency':client.frequency,'cycle':client.cycle,'recommendations':recs[['reason','action']].to_dict('records')}
        try:
            with st.spinner('Модель готовит текст…'): draft=api.draft(model,facts)
            st.session_state[f'client_draft_{cid}']=draft
        except ProviderError as exc: st.error(str(exc))
