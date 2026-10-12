"""Financial and date-boundary regression checks for batched calculations."""
import unittest

import pandas as pd

from sales_center.analytics import client_summary, orders
from sales_center.recommendations import generate


class BatchAnalyticsTests(unittest.TestCase):
    def test_order_totals_keep_unknown_cost_and_individual_cycle(self):
        clients = pd.DataFrame([
            (1, 'Первый', 'Ресторан', 'Москва'),
            (2, 'Без покупок', 'Магазин', 'Москва'),
        ], columns=['client_id', 'company', 'segment', 'city'])
        lines = pd.DataFrame([
            (11, 1, '2026-08-01', 10., 1., 9.),
            (11, 1, '2026-08-01', 20., float('nan'), float('nan')),
            (12, 1, '2026-09-01', 20., 2., 18.),
        ], columns=['order_id', 'client_id', 'date', 'revenue', 'cost', 'profit'])
        lines['date'] = pd.to_datetime(lines.date)
        purchases = orders(lines).set_index('order_id')
        self.assertEqual(purchases.loc[11, 'revenue'], 30.)
        self.assertTrue(pd.isna(purchases.loc[11, 'cost']))
        self.assertTrue(pd.isna(purchases.loc[11, 'profit']))
        summary = client_summary(clients, lines, '2026-10-12').set_index('client_id')
        self.assertEqual(summary.loc[1, 'order_count'], 2)
        self.assertEqual(summary.loc[1, 'revenue'], 50.)
        self.assertEqual(summary.loc[1, 'average'], 25.)
        self.assertEqual(summary.loc[1, 'mean_gap'], 31.)
        self.assertTrue(pd.isna(summary.loc[1, 'cycle']))
        self.assertEqual(summary.loc[1, 'days_since'], 41)
        self.assertAlmostEqual(summary.loc[1, 'frequency'], 60/72)
        self.assertEqual(summary.loc[2, 'order_count'], 0)
        self.assertEqual(summary.loc[2, 'average'], 0.)
        self.assertEqual(summary.loc[2, 'frequency'], 0.)
        self.assertTrue(pd.isna(summary.loc[2, 'last_order']))

    def test_monthly_decline_and_growth_use_orders_and_exact_boundaries(self):
        today = pd.Timestamp('2026-10-12')
        clients = pd.DataFrame([
            (1, 'Снижение', 'Ресторан', 'Москва'),
            (2, 'Рост', 'Магазин', 'Москва'),
        ], columns=['client_id', 'company', 'segment', 'city'])
        records = [(1, 1, pd.Timestamp('2026-07-03'), 300.),
                   (2, 1, pd.Timestamp('2026-08-03'), 200.),
                   (3, 1, pd.Timestamp('2026-09-03'), 100.)]
        records += [(10+index, 2, today-pd.Timedelta(days=days), amount)
                    for index, (days, amount) in enumerate([
                        (121, 10000.), (120, 100.), (61, 100.), (60, 200.), (0, 200.)])]
        lines = pd.DataFrame(records, columns=['order_id', 'client_id', 'date', 'revenue'])
        # A multi-line order must contribute one average-check observation.
        split = lines[lines.order_id == 13].copy()
        lines.loc[lines.order_id == 13, 'revenue'] = 100.
        split['revenue'] = 100.
        lines = pd.concat([lines, split], ignore_index=True)
        lines['cost'] = lines.revenue*.5
        lines['profit'] = lines.revenue-lines.cost
        lines['category'] = 'Сыры'
        products = pd.DataFrame(columns=['category', 'product', 'price'])
        summary = client_summary(clients, lines, today)
        recommendations = generate(summary, lines, products, today).set_index('id')
        self.assertEqual(recommendations.loc['1:decline', 'effect'], 200)
        self.assertIn('300 → 200 → 100', recommendations.loc['1:decline', 'reason'])
        self.assertIn('на 100%', recommendations.loc['2:growth', 'reason'])
        self.assertEqual(recommendations.loc['2:growth', 'effect'], 318)


if __name__ == '__main__':
    unittest.main()
