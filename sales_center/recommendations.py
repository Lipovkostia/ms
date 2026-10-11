"""Explainable rules; estimates are not actual sales or stock commitments."""
import pandas as pd
from .analytics import orders

def generate(summary, lines, products, today):
    rows = []
    client_lines = dict(tuple(lines.groupby('client_id')))
    client_orders = dict(tuple(orders(lines).groupby('client_id')))
    today = pd.Timestamp(today)
    recent_end = today.replace(day=1)
    def add(c, kind, title, reason, action, effect, priority):
        rows.append(dict(id=f'{c.client_id}:{kind}', client_id=c.client_id, company=c.company,
                         kind=kind, title=title, reason=reason, action=action,
                         effect=round(float(effect)), priority=priority))
    for c in summary.itertuples():
        own = client_lines.get(c.client_id)
        if own is None or own.empty:
            continue
        if pd.notna(c.cycle_ratio) and c.cycle_ratio > 1.5:
            add(c, 'return', 'Восстановить цикл закупок',
                f'Обычный цикл: {c.cycle:.0f} дн.; после последнего заказа прошло {c.days_since:.0f} дн. ({c.cycle_ratio:.1f}× цикла).',
                'Уточнить остатки клиента и потребность в следующем заказе.', c.average, 'Высокий')
        cats = set(own.category)
        if 'Хамон' in cats and 'Оливки' not in cats and not products[products.category == 'Оливки'].empty and products[products.category == 'Оливки'].price.notna().all():
            olive = products[products.category == 'Оливки'].iloc[0]
            add(c, 'cross', 'Предложить оливки к хамону',
                'Клиент покупает хамон; в доступной истории нет оливок. Это гипотеза для обсуждения.',
                f'Уточнить интерес к товару «{olive["product"]}». Проверить цену и наличие перед предложением.', float(olive.price)*6, 'Средний')
        totals = []
        for back in [3, 2, 1]:
            start = recent_end-pd.DateOffset(months=back)
            end = start+pd.DateOffset(months=1)
            totals.append(float(own[(own.date >= start) & (own.date < end)].revenue.sum()))
        if totals[0] > totals[1] > totals[2] and totals[0] > 0:
            add(c, 'decline', 'Обсудить снижение оборота',
                f'Оборот за три полных месяца: {totals[0]:,.0f} → {totals[1]:,.0f} → {totals[2]:,.0f} ₽.',
                'Выяснить причины снижения закупок и согласовать ассортимент.', totals[0]-totals[2], 'Высокий')
        o = client_orders[c.client_id]
        curr = o[o.date >= today-pd.Timedelta(days=60)]
        prev = o[(o.date < today-pd.Timedelta(days=60)) & (o.date >= today-pd.Timedelta(days=120))]
        if len(curr) >= 2 and len(prev) >= 2 and curr.revenue.mean() > prev.revenue.mean()*1.2:
            add(c, 'growth', 'Развить рост среднего чека',
                f'Средний чек последних 60 дней выше предыдущих 60 дней на {(curr.revenue.mean()/prev.revenue.mean()-1)*100:.0f}%.',
                'Обсудить расширение ассортимента под растущую потребность.', c.average*.15, 'Средний')
    return pd.DataFrame(rows, columns=['id','client_id','company','kind','title','reason','action','effect','priority'])

def message(company, action):
    return f'Здравствуйте!\n\nХотел бы обсудить следующие закупки для {company}. {action}\n\nПодскажите, пожалуйста, какие позиции сейчас актуальны и когда удобно связаться? Цены и наличие уточню перед согласованием заказа.'
