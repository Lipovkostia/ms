from pathlib import Path
from datetime import date
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from sales_center.storage import Store
from fixtures import demo_data

ROOT=Path(__file__).resolve().parents[1]

class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'records.db')
        self.patch=patch('sales_center.storage.Store',return_value=self.store)
        self.patch.start()
        self.cache_patch=patch('sales_center.snapshots.Store',return_value=self.store)
        self.cache_patch.start()
    def tearDown(self):
        self.cache_patch.stop();self.patch.stop();self.temp.cleanup()
    def app(self,loaded=True):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30)
        at.secrets.clear()
        at.session_state['device_ready']=True
        if loaded:
            c,p,l=demo_data(date.today());c.attrs['account_id']='test-account'
            at.session_state['live_data']=(c,p,l)
        at.run()
        self.assertFalse(at.exception)
        return at
    def test_all_sections(self):
        at=self.app()
        for page in next(r for r in at.radio if r.key=='page').options:
            next(r for r in at.radio if r.key=='page').set_value(page).run()
            self.assertFalse(at.exception,page)
            self.assertIn(at.session_state['page'],[t.value for t in at.title])
    def test_empty_source_no_demo_fallback(self):
        at=self.app(False)
        self.assertEqual(len(at.metric),0)
        with patch.dict('os.environ',{},clear=True):
            next(b for b in at.button if b.label=='Загрузить / обновить данные').click().run()
        self.assertTrue(at.error)
        self.assertFalse(at.exception)
    def test_search_and_saved_draft_task(self):
        at=self.app()
        next(r for r in at.radio if r.key=='page').set_value('Клиенты').run()
        next(t for t in at.text_input if t.label.startswith('Поиск')).set_value('несуществующий').run()
        self.assertTrue(any('не найдены' in i.value for i in at.info))
        next(t for t in at.text_input if t.label.startswith('Поиск')).set_value('').run()
        draft=next(t for t in at.text_area if t.label=='Черновик сообщения')
        draft.set_value('Обсудим заказ').run()
        next(b for b in at.button if b.label=='Сохранить черновик').click().run()
        self.assertFalse(at.exception)
        next(b for b in at.button if b.label=='Создать задачу').click().run()
        self.assertEqual(len(self.store.tasks()),1)
        next(r for r in at.radio if r.key=='page').set_value('Задачи').run()
        next(s for s in at.selectbox if s.label=='Статус').set_value('Выполнена')
        next(b for b in at.button if b.label=='Сохранить изменения').click().run()
        self.assertEqual(self.store.tasks().iloc[0]['status'],'Выполнена')
    def test_success_and_failed_refresh_preserves_snapshot(self):
        at=self.app(False)
        fresh=demo_data(date.today());fresh[0].attrs['account_id']='test-account'
        with patch('sales_center.sync.load_live',return_value=fresh) as api:
            next(t for t in at.text_input if t.label=='API-токен Моего Склада').set_value('test-only')
            next(b for b in at.button if b.label=='Загрузить / обновить данные').click().run()
            self.assertFalse(at.exception)
            self.assertEqual(api.call_count,1)
            self.assertIn('live_analytics',at.session_state)
        from sales_center.moysklad import MoySkladError
        with patch('sales_center.sync.load_live',side_effect=MoySkladError('Ошибка тестового API')):
            next(b for b in at.button if b.label=='Загрузить / обновить данные').click().run()
        self.assertTrue(at.error)
        self.assertEqual(len(at.session_state['live_data'][0]),100)
        self.assertFalse(at.exception)
    def test_invalid_dates(self):
        at=self.app()
        next(d for d in at.date_input if d.label=='Начало периода').set_value(date(2030,1,1)).run()
        self.assertTrue(at.error)
        self.assertFalse(at.exception)

    def test_managed_secret_survives_new_session_with_cached_data(self):
        fresh=demo_data(date.today());fresh[0].attrs['account_id']='test-account'
        def managed_app():
            at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30)
            at.secrets.clear()
            at.secrets['MOYSKLAD_TOKEN']='persistent-test-key'
            at.secrets['MOYSKLAD_PRIVATE_DEPLOYMENT']=True
            return at
        first=managed_app()
        with patch('sales_center.sync.load_live',return_value=fresh) as api:
            first.run();self.assertFalse(first.exception)
            self.assertEqual(api.call_count,1)
        second=managed_app()
        with patch('sales_center.sync.load_live') as api:
            second.run();self.assertFalse(second.exception)
            self.assertTrue(second.session_state['sync_restored'])
            self.assertEqual(len(second.session_state['live_data'][0]),100)
            next(r for r in second.radio if r.key=='page').set_value('Главная').run()
            api.assert_not_called()
            self.assertFalse(second.exception)
        self.assertEqual(second.session_state['sync_interval'],30)
    def test_public_app_does_not_expose_server_token(self):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30)
        at.secrets.clear()
        at.secrets['MOYSKLAD_TOKEN']='persistent-test-key'
        with patch('sales_center.sync.load_live') as api:
            at.run();api.assert_not_called()
        self.assertFalse(at.exception)
        self.assertNotIn('live_data',at.session_state)
    def test_revoking_managed_access_clears_existing_session(self):
        fresh=demo_data(date.today());fresh[0].attrs['account_id']='test-account'
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30)
        at.secrets.clear()
        at.secrets['MOYSKLAD_TOKEN']='persistent-test-key'
        at.secrets['MOYSKLAD_PRIVATE_DEPLOYMENT']=True
        with patch('sales_center.sync.load_live',return_value=fresh): at.run()
        self.assertIn('live_data',at.session_state)
        at.secrets['MOYSKLAD_PRIVATE_DEPLOYMENT']=False
        with patch('sales_center.sync.load_live') as api:
            at.run();api.assert_not_called()
        self.assertFalse(at.exception)
        self.assertNotIn('live_data',at.session_state)
        self.assertNotIn('sync_token',at.session_state)

    def test_settings_buttons_open_working_settings_without_connection(self):
        at=self.app(False)
        next(b for b in at.button if b.key=='open_settings').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['page'],'Настройки')
        self.assertIn('Настройки',[title.value for title in at.title])
        at=self.app(False)
        next(b for b in at.button if b.key=='sync_settings').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['page'],'Настройки')
    def test_price_list_buyer_opens_correct_client_and_clears_filters(self):
        at=self.app()
        next(r for r in at.radio if r.key=='page').set_value('Товарная аналитика').run()
        self.assertFalse(at.exception)
        first=next(b for b in at.button if b.key and b.key.startswith('price_buyer_'))
        target=int(first.key.removeprefix('price_buyer_'))
        first.click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['page'],'Клиенты')
        self.assertEqual(at.session_state['workspace_client'],target)
        self.assertEqual(at.session_state['global_search'],'')
        self.assertEqual(at.session_state['clients_priorities'],[])
