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
    def tearDown(self):
        self.patch.stop();self.temp.cleanup()
    def app(self,loaded=True):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30)
        if loaded:
            c,p,l=demo_data(date.today());c.attrs['account_id']='test-account'
            at.session_state['live_data']=(c,p,l)
        at.run()
        self.assertFalse(at.exception)
        return at
    def test_all_sections(self):
        at=self.app()
        for page in at.radio[0].options:
            at.radio[0].set_value(page).run()
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
        at.radio[0].set_value('Клиенты').run()
        next(t for t in at.text_input if t.label.startswith('Поиск')).set_value('несуществующий').run()
        self.assertTrue(any('не найдены' in i.value for i in at.info))
        next(t for t in at.text_input if t.label.startswith('Поиск')).set_value('').run()
        draft=next(t for t in at.text_area if t.label=='Черновик сообщения')
        draft.set_value('Обсудим заказ').run()
        next(b for b in at.button if b.label=='Сохранить черновик').click().run()
        self.assertFalse(at.exception)
        next(b for b in at.button if b.label=='Создать задачу').click().run()
        self.assertEqual(len(self.store.tasks()),1)
        at.radio[0].set_value('Задачи').run()
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
