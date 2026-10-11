"""Pure, auditable calculations. A line is not an order."""
import pandas as pd

def orders(lines):
    if lines.empty:
        return lines[['order_id', 'client_id', 'date', 'revenue', 'cost', 'profit']].copy()
    return lines.groupby(['order_id', 'client_id', 'date'], as_index=False)[['revenue', 'cost', 'profit']].agg(lambda v: v.sum() if v.notna().all() else float('nan'))

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
    all_orders = orders(lines)
    rows = []
    for c in clients.itertuples():
        o = all_orders[all_orders.client_id == c.client_id].sort_values('date')
        gaps = o.date.diff().dt.days.dropna()
        # Robust median avoids a single missed order redefining the normal cycle.
        cycle = float(gaps.median()) if len(gaps) >= 2 else None
        mean_gap = float(gaps.mean()) if len(gaps) else None
        last = o.date.max() if len(o) else pd.NaT
        days = int((today-last).days) if len(o) else None
        ratio = days/cycle if cycle and days is not None else None
        priority = 'Высокий' if ratio is not None and ratio > 1.5 else 'Средний' if ratio is not None and ratio > 1.1 else 'Низкий'
        age = max(1, (today-o.date.min()).days) if len(o) else 1
        rows.append(dict(client_id=c.client_id, company=c.company, segment=c.segment, city=c.city,
                         revenue=float(o.revenue.sum()), average=float(o.revenue.mean()) if len(o) else 0,
                         order_count=len(o), last_order=last, days_since=days, cycle=cycle,
                         mean_gap=mean_gap, cycle_ratio=ratio, frequency=len(o)*30/age, priority=priority))
    return pd.DataFrame(rows)

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
