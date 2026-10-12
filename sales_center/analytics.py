"""Pure, auditable calculations. A line is not an order."""
import pandas as pd

def orders(lines):
    if lines.empty:
        return lines[['order_id', 'client_id', 'date', 'revenue', 'cost', 'profit']].copy()
    amounts = ['revenue', 'cost', 'profit']
    grouped = lines.groupby(['order_id', 'client_id', 'date'])
    # Unknown cost/profit on one line makes the whole order unknown. Native
    # reductions preserve that rule without invoking Python for every order.
    complete = grouped[amounts].count().eq(grouped.size(), axis='index')
    return grouped[amounts].sum(min_count=1).where(complete).reset_index()

def metrics(lines):
    revenue = float(lines.revenue.sum())
    profit = float(lines.profit.sum()) if lines.profit.notna().all() else float('nan')
    count = int(lines.order_id.nunique())
    return dict(revenue=revenue, profit=profit, orders=count,
                average=revenue/count if count else 0,
                margin=profit/revenue*100 if revenue else 0,
                quantity=float(lines.quantity.sum()))

def client_summary(clients, lines, today):
    today = pd.Timestamp(today).normalize()
    all_orders = orders(lines).sort_values(['client_id', 'date'])
    all_orders['gap'] = all_orders.groupby('client_id').date.diff().dt.days
    totals = all_orders.groupby('client_id').agg(
        revenue=('revenue', 'sum'), average=('revenue', 'mean'),
        order_count=('order_id', 'size'), last_order=('date', 'max'),
        first_order=('date', 'min'), cycle=('gap', 'median'),
        gap_count=('gap', 'count'), mean_gap=('gap', 'mean'))
    # Robust median needs at least two intervals, as in the original formula.
    totals['cycle'] = totals.cycle.where(totals.gap_count >= 2)
    result = clients[['client_id', 'company', 'segment', 'city']].merge(
        totals, left_on='client_id', right_index=True, how='left', sort=False)
    result['average'] = result.average.where(result.order_count.notna(), 0)
    result[['revenue', 'order_count']] = result[['revenue', 'order_count']].fillna(0)
    result['order_count'] = result.order_count.astype('int64')
    result['days_since'] = (today-result.last_order).dt.days
    result['cycle_ratio'] = result.days_since/result.cycle.where(result.cycle != 0)
    result['frequency'] = result.order_count*30/(today-result.first_order).dt.days.clip(lower=1)
    result['frequency'] = result.frequency.fillna(0)
    result['priority'] = 'Низкий'
    result.loc[result.cycle_ratio > 1.1, 'priority'] = 'Средний'
    result.loc[result.cycle_ratio > 1.5, 'priority'] = 'Высокий'
    return result[['client_id', 'company', 'segment', 'city', 'revenue', 'average',
                   'order_count', 'last_order', 'days_since', 'cycle', 'mean_gap',
                   'cycle_ratio', 'frequency', 'priority']].reset_index(drop=True)

def period(lines, start, end):
    return lines[(lines.date >= pd.Timestamp(start)) & (lines.date < pd.Timestamp(end)+pd.Timedelta(days=1))]

def monthly(lines):
    frame = lines.copy()
    frame['month'] = frame.date.dt.to_period('M').dt.to_timestamp()
    return frame.groupby('month', as_index=False)[['revenue', 'profit']].agg(lambda v: v.sum() if v.notna().all() else float('nan'))

def companions(lines):
    """Count orders containing both products, once per product pair per order."""
    pairs = {}
    from itertools import combinations
    for _, group in lines.groupby('order_id'):
        for a, b in combinations(sorted(set(group['product'])), 2):
            pairs[a, b] = pairs.get((a, b), 0)+1
    return pd.DataFrame([(a, b, n) for (a, b), n in pairs.items()], columns=['Товар', 'Сопутствующий товар', 'Совместных заказов']).sort_values('Совместных заказов', ascending=False)
