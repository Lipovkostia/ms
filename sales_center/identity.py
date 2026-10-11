import hashlib
import streamlit as st

def identity():
    try: configured='auth' in st.secrets
    except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError): configured=False
    if configured:
        if not st.user.is_logged_in:
            st.title('Вход в AI-центр продаж')
            st.write('Войдите в свой аккаунт, чтобы открыть клиентскую базу.')
            if st.button('Войти'): st.login()
            st.stop()
        email=st.user.get('email')
        if not email: st.error('Провайдер входа не вернул email.');st.stop()
        try: allowed=st.secrets.get('allowed_emails',[])
        except Exception: allowed=[]
        if not allowed or email not in allowed:
            st.error('Доступ не разрешён. Администратор должен добавить email в allowed_emails.')
            if st.button('Выйти'): st.logout()
            st.stop()
        return hashlib.sha256(email.encode()).hexdigest(),email
    return 'personal','Персональный режим'
