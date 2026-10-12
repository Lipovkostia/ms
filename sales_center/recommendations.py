"""Explainable rules; estimates are not actual sales or stock commitments."""
import pandas as pd
from .analytics import orders

def generate(summary, lines, products, today):
    rows = []
    categories = lines.groupby('client_id').category.agg(set).to_dict()
    all_orders = orders(lines)
    today = pd.Timestamp(today)
    recent_end = today.replace(day=1)
    month_starts = [recent_end-pd.DateOffset(months=back) for back in [3, 2, 1]]
    monthly_totals = [lines[(lines.date >= start) & (lines.date < start+pd.DateOffset(months=1))]
                      .groupby('client_id').revenue.sum().to_dict() for start in month_starts]
    cutoff = today-pd.Timedelta(days=60)
    current = all_orders[all_orders.date >= cutoff].groupby('client_id').revenue.agg(['size', 'mean'])
    previous = all_orders[(all_orders.date < cutoff) & (all_orders.date >= today-pd.Timedelta(days=120))]\
        .groupby('client_id').revenue.agg(['size', 'mean'])
    growth = current.join(previous, how='inner', lsuffix='_current', rsuffix='_previous')
    growth = growth[(growth.size_current >= 2) & (growth.size_previous >= 2) &
                    (growth.mean_current > growth.mean_previous*1.2)]
    growth_percent = ((growth.mean_current/growth.mean_previous-1)*100).to_dict()
    olives = products[products.category == 'Оливки']
    olive = olives.iloc[0] if not olives.empty and olives.price.notna().all() else None
    def add(c, kind, title, reason, action, effect, priority):
        rows.append(dict(id=f'{c.client_id}:{kind}', client_id=c.client_id, company=c.company,
                         kind=kind, title=title, reason=reason, action=action,
                         effect=round(float(effect)), priority=priority))
    for c in summary.itertuples():
        cats = categories.get(c.client_id)
        if cats is None:
            continue
        if pd.notna(c.cycle_ratio) and c.cycle_ratio > 1.5:
            add(c, 'return', 'Восстановить цикл закупок',
                f'Обычный цикл: {c.cycle:.0f} дн.; после последнего заказа прошло {c.days_since:.0f} дн. ({c.cycle_ratio:.1f}× цикла).',
                'Уточнить остатки клиента и потребность в следующем заказе.', c.average, 'Высокий')
        if 'Хамон' in cats and 'Оливки' not in cats and olive is not None:
            add(c, 'cross', 'Предложить оливки к хамону',
                'Клиент покупает хамон; в доступной истории нет оливок. Это гипотеза для обсуждения.',
                f'Уточнить интерес к товару «{olive["product"]}». Проверить цену и наличие перед предложением.', float(olive.price)*6, 'Средний')
        totals = [float(month.get(c.client_id, 0)) for month in monthly_totals]
        if totals[0] > totals[1] > totals[2] and totals[0] > 0:
            add(c, 'decline', 'Обсудить снижение оборота',
                f'Оборот за три полных месяца: {totals[0]:,.0f} → {totals[1]:,.0f} → {totals[2]:,.0f} ₽.',
                'Выяснить причины снижения закупок и согласовать ассортимент.', totals[0]-totals[2], 'Высокий')
        if c.client_id in growth_percent:
            add(c, 'growth', 'Развить рост среднего чека',
                f'Средний чек последних 60 дней выше предыдущих 60 дней на {growth_percent[c.client_id]:.0f}%.',
                'Обсудить расширение ассортимента под растущую потребность.', c.average*.15, 'Средний')
    return pd.DataFrame(rows, columns=['id','client_id','company','kind','title','reason','action','effect','priority'])

def message(company, action):
    return f'Здравствуйте!\n\nХотел бы обсудить следующие закупки для {company}. {action}\n\nПодскажите, пожалуйста, какие позиции сейчас актуальны и когда удобно связаться? Цены и наличие уточню перед согласованием заказа.'
