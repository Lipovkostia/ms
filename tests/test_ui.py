import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from sales_center.storage import Store

ROOT = Path(__file__).resolve().parents[1]

class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name)/'sales.db')
        self.patch = patch('sales_center.storage.Store', return_value=self.store)
        self.patch.start()
    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()
    def app(self):
        at = AppTest.from_file(str(ROOT/'app.py'),default_timeout=30)
        at.run()
        self.assertFalse(at.exception)
        return at
    def test_all_sections(self):
        at = self.app()
        pages = list(at.radio[0].options)
        for page in pages:
            at.radio[0].set_value(page).run()
            self.assertFalse(at.exception, page)
            self.assertIn(page,[t.value for t in at.title])
    def test_search_filters_and_card(self):
        at = self.app()
        at.radio[0].set_value('Клиенты').run()
        at.text_input[0].set_value('несуществующий').run()
        self.assertEqual(len(at.dataframe[0].value),0)
        at.text_input[0].set_value('Гастро').run()
        self.assertGreater(len(at.dataframe[0].value),0)
        at.multiselect[0].set_value(['Ресторан']).run()
        self.assertTrue((at.dataframe[0].value['Сегмент']=='Ресторан').all())
        at.button[0].click().run()
        self.assertEqual(at.radio[0].value,'Карточка клиента')
        self.assertFalse(at.exception)
    def test_task_and_draft(self):
        at = self.app()
        at.radio[0].set_value('Карточка клиента').run()
        draft = next(x for x in at.text_area if x.label == 'Черновик сообщения')
        draft.set_value('Здравствуйте! Уточним следующий заказ.').run()
        self.assertEqual(at.code[0].value,'Здравствуйте! Уточним следующий заказ.')
        button = next(b for b in at.button if b.label == 'Создать задачу')
        button.click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(self.store.tasks()),1)
        at.radio[0].set_value('Задачи').run()
        status = next(s for s in at.selectbox if s.label=='Статус')
        status.set_value('Выполнена')
        result = next(t for t in at.text_area if t.label=='Заметка о результате')
        result.set_value('Договорились о контакте')
        next(b for b in at.button if b.label=='Сохранить изменения').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(self.store.tasks().iloc[0]['status'],'Выполнена')
    def test_real_source_does_not_fallback(self):
        at = self.app()
        next(s for s in at.selectbox if s.label == 'Источник данных').set_value('Мой Склад').run()
        self.assertFalse(at.exception)
        self.assertTrue(any('Подключение' in t.value for t in at.title))
        with patch.dict('os.environ', {}, clear=True):
            next(b for b in at.button if b.label == 'Загрузить / обновить данные').click().run()
        self.assertTrue(at.error)
        self.assertFalse(at.exception)

    def test_process_recommendation(self):
        at = self.app()
        next(b for b in at.button if b.label == 'Отметить обработанной').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(self.store.processed()), 1)
        at.radio[0].set_value('Эффективность').run()
        self.assertTrue(any(m.label == 'Обработано рекомендаций за период' and m.value == '1' for m in at.metric))

    def test_invalid_dates(self):
        at = self.app()
        at.date_input[0].set_value(at.date_input[1].value.replace(year=2030)).run()
        self.assertFalse(at.exception)
        self.assertTrue(at.error)

if __name__ == '__main__':
    unittest.main()
