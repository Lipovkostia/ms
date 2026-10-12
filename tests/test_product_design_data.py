from datetime import date
from io import BytesIO
import unittest

import pandas as pd

from sales_center.product_analytics import buyers
from sales_center.product_design_data import (
    catalog_view, export_catalog_csv, filter_sales, period_window, warehouse_options,
)


class ProductDesignDataTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 10, 12)
        self.pid = 2**59 + 123
        rows = [
            (self.pid, 'Сыр', 'Испания/Сыры', 'SR-1', 'MAN', 'кг', 900, False),
            (self.pid + 1, 'Сыр', 'Испания/Сыры/Мягкие', 'SR-2', 'BRI', 'шт.', 1000, False),
            (3, 'Оливки', 'Испания/Сырые продукты', 'OL-3', 'OLV', 'банка', 300, False),
            (4, 'Без продаж', 'Испания/Сыры', 'SR-4', '', 'кг', 400, False),
            (5, 'Архивный', 'Испания/Сыры', 'SR-5', '', 'кг', 500, True),
            (6, 'Нет цены', 'Испания/Сыры', 'SR-6', '', 'кг', 0, False),
        ]
        self.products = pd.DataFrame(rows, columns=[
            'product_id', 'product', 'category', 'code', 'article', 'unit', 'price', 'archived',
        ])
        self.products['entity_type'] = 'product'
        self.products['sale_prices'] = [
            [{'id': 'wholesale', 'name': 'Опт', 'value': float(price), 'currency': 'RUB'},
             {'id': 'retail', 'name': 'Розница', 'value': float(price) * 2, 'currency': 'EUR'}]
            for price in self.products.price
        ]
        self.lines = pd.DataFrame([
            ('old', 10, self.pid, '2026-09-12', 20, 9000, 'w1', 'Первый'),
            ('a', 10, self.pid, '2026-09-13', 1.5, 100, 'w1', 'Первый'),
            ('a', 10, self.pid, '2026-09-13', 2.5, 200, 'w1', 'Первый'),
            ('b', 11, self.pid, '2026-10-12 23:59:59', 3, 300, 'w2', 'Второй'),
            ('c', 10, self.pid + 1, '2026-10-11', 12, 400, 'w1', 'Первый'),
            ('d', 10, 3, '2026-10-11', 50, 500, 'w1', 'Первый'),
            ('e', 10, self.pid, '2026-10-12', 0, 90, 'w1', 'Первый'),
            ('f', 10, self.pid, '2026-10-12', -4, -100, 'w1', 'Первый'),
            ('future', 10, self.pid, '2026-10-13', 20, 700, 'w1', 'Первый'),
        ], columns=['order_id', 'client_id', 'product_id', 'date', 'quantity', 'revenue', 'warehouse_id', 'warehouse'])
        self.lines['date'] = pd.to_datetime(self.lines.date, format='mixed')
        self.clients = pd.DataFrame({'client_id': [10, 11], 'company': ['Покупатель А', 'Покупатель Б']})

    def test_period_is_inclusive_and_never_claims_unloaded_history(self):
        start, end = period_window(self.lines, self.today, '30')
        self.assertEqual(start, pd.Timestamp('2026-09-13'))
        sales = filter_sales(self.lines, start, end)
        self.assertEqual(set(sales.order_id), {'a', 'b', 'c', 'd'})
        for key in ['90', '12m', 'all']:
            self.assertEqual(period_window(self.lines, self.today, key)[0], pd.Timestamp('2026-09-12'))
        self.assertEqual(period_window(self.lines.iloc[:0], self.today, 'all'),
                         (pd.Timestamp(self.today), pd.Timestamp(self.today)))
        with self.assertRaises(ValueError):
            period_window(self.lines, self.today, 'unsupported')

    def test_catalog_and_buyer_panel_share_actual_filtered_totals(self):
        start, end = period_window(self.lines, self.today, '30')
        sales = filter_sales(self.lines, start, end)
        catalog = catalog_view(self.products, sales, 'wholesale', category='Испания/Сыры', only_sales=True)
        self.assertEqual(set(catalog.product_id), {self.pid, self.pid + 1})
        selected = catalog.set_index('product_id').loc[self.pid]
        customer_rows = buyers(sales, self.clients, self.pid, self.today)
        self.assertEqual(selected.sold_revenue, 600)
        self.assertEqual(selected.sold_quantity, 7)
        self.assertEqual(selected.sold_orders, 2)
        self.assertEqual(selected.sold_buyers, 2)
        self.assertEqual(selected.sold_revenue, customer_rows.revenue.sum())
        self.assertEqual(selected.sold_quantity, customer_rows.quantity.sum())
        self.assertEqual(selected.list_price, 900)
        self.assertEqual(selected.unit, 'кг')
        # The identically named other product must stay distinct, even with large IDs.
        self.assertEqual(catalog.set_index('product_id').loc[self.pid + 1].sold_quantity, 12)

    def test_exact_buyer_and_warehouse_filters(self):
        start, end = period_window(self.lines, self.today, '30')
        self.assertEqual(warehouse_options(self.lines), {'w2': 'Второй', 'w1': 'Первый'})
        sales = filter_sales(self.lines, start, end, buyer_id=11, warehouse_id='w2')
        self.assertEqual(sales.order_id.tolist(), ['b'])
        catalog = catalog_view(self.products, sales, 'wholesale', only_sales=True)
        self.assertEqual(catalog.product_id.tolist(), [self.pid])
        self.assertEqual(catalog.iloc[0].sold_revenue, 300)
        self.assertEqual(warehouse_options(self.lines.drop(columns=['warehouse_id', 'warehouse'])), {})
        name_only = self.lines.drop(columns='warehouse_id')
        self.assertEqual(warehouse_options(name_only), {'Второй': 'Второй', 'Первый': 'Первый'})
        self.assertEqual(filter_sales(name_only, start, end, warehouse_id='Второй').order_id.tolist(), ['b'])
        with self.assertRaises(ValueError):
            filter_sales(self.lines, start, end, warehouse_id='unknown')

    def test_search_category_and_active_price_rules_are_preserved(self):
        sales = filter_sales(self.lines, *period_window(self.lines, self.today, '30'))
        for query in ['MAN', 'sr-1', 'сыр']:
            result = catalog_view(self.products, sales, 'wholesale', query=query)
            self.assertIn(self.pid, result.product_id.tolist())
        all_rows = catalog_view(self.products, sales, 'wholesale')
        self.assertEqual(set(all_rows.product_id), {self.pid, self.pid + 1, 3, 4})
        self.assertEqual(all_rows.set_index('product_id').loc[4].sold_revenue, 0)
        self.assertNotIn(5, catalog_view(self.products, sales, 'wholesale', positive=False).product_id.tolist())
        self.assertIn(6, catalog_view(self.products, sales, 'wholesale', positive=False).product_id.tolist())
        self.assertTrue(catalog_view(self.products, sales, 'wholesale', query='not found').empty)
        self.assertTrue(catalog_view(self.products, sales, 'missing price').empty)

    def test_sorting_and_export_follow_same_filtered_price_list(self):
        sales = filter_sales(self.lines, *period_window(self.lines, self.today, '30'))
        result = catalog_view(self.products, sales, 'retail', category='Испания/Сыры', only_sales=True)
        self.assertEqual(result.product_id.tolist(), [self.pid, self.pid + 1])
        by_price = catalog_view(self.products, sales, 'retail', category='Испания/Сыры', only_sales=True, sort='price')
        self.assertEqual(by_price.product_id.tolist(), [self.pid + 1, self.pid])
        by_quantity = catalog_view(self.products, sales, 'retail', only_sales=True, sort='quantity')
        self.assertEqual(by_quantity.product_id.tolist(), [3, self.pid + 1, self.pid])
        by_name = catalog_view(self.products, sales, 'retail', only_sales=True, sort='name')
        self.assertEqual(by_name.iloc[0]['product'], 'Оливки')
        exported = pd.read_csv(BytesIO(export_catalog_csv(by_price)))
        self.assertEqual(exported['ID товара'].tolist(), [self.pid + 1, self.pid])
        self.assertEqual(exported['Цена прайс-листа'].tolist(), [2000, 1800])
        self.assertEqual(exported['Валюта цены'].tolist(), ['EUR', 'EUR'])
        self.assertEqual(exported['Единица измерения'].tolist(), ['шт.', 'кг'])
        self.assertEqual(exported['Выручка без НДС, ₽'].sum(), 1000)
        with self.assertRaises(ValueError):
            catalog_view(self.products, sales, 'retail', sort='unsupported')

    def test_empty_source_remains_empty_and_csv_text_does_not_execute(self):
        result = catalog_view(self.products, self.lines.iloc[:0], 'wholesale', only_sales=True)
        self.assertTrue(result.empty)
        self.assertIn('Выручка без НДС, ₽', export_catalog_csv(result).decode('utf-8-sig'))
        result = catalog_view(self.products, self.lines.iloc[:0], 'wholesale')
        result.loc[0, 'product'] = '=DANGEROUS()'
        exported = pd.read_csv(BytesIO(export_catalog_csv(result)))
        self.assertEqual(exported.iloc[0]['Товар'], "'=DANGEROUS()")


if __name__ == '__main__':
    unittest.main()
