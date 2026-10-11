"""Escaped HTML and compact charts for the CRM workspace; no data generation."""
from html import escape
import pandas as pd
import plotly.express as px
from .analytics import monthly


def safe(value):
    return escape(str(value),quote=True)


def money(value):
    return f'{value:,.0f} ₽'.replace(',', ' ') if pd.notna(value) else 'Нет данных'


def pill(label,tone='mint'):
    return f'<span class="pill pill-{safe(tone)}">{safe(label)}</span>'


def stat(label,value,detail,icon,tone='blue'):
    return f'<div class="stat-card stat-{safe(tone)}"><div class="stat-icon">{safe(icon)}</div><div><div class="stat-label">{safe(label)}</div><div class="stat-value">{safe(value)}</div><div class="stat-detail">{safe(detail)}</div></div></div>'


def client_row(client,selected=False):
    tone={'Высокий':'orange','Средний':'blue','Низкий':'gray'}.get(client.priority,'gray')
    last=client.last_order.strftime('%d.%m.%Y') if pd.notna(client.last_order) else 'нет покупок'
    return f'<div class="client-row {"selected" if selected else ""}"><div>{pill(client.priority,tone)}<strong>{safe(client.company)}</strong></div><p>{safe(client.city)}</p><p>Последний заказ: {safe(last)}</p><div class="client-bottom"><b>{money(client.revenue)}</b><span>за 12 месяцев</span></div></div>'


def chart_style(fig,height=215):
    fig.update_layout(height=height,margin=dict(l=5,r=5,t=8,b=10),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font=dict(family='Arial, sans-serif',size=11,color='#526383'),showlegend=False)
    fig.update_xaxes(title=None,showgrid=False)
    fig.update_yaxes(title=None,gridcolor='#edf1f7',zeroline=False)
    return fig


def purchase_chart(lines):
    data=monthly(lines).rename(columns={'month':'Месяц','revenue':'Оборот'})
    fig=px.bar(data,x='Месяц',y='Оборот',color_discrete_sequence=['#91dfbf'])
    fig.update_traces(marker_line_width=0,hovertemplate='%{x|%m.%Y}<br>%{y:,.0f} ₽<extra></extra>')
    months=['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']
    fig.update_xaxes(tickmode='array',tickvals=data['Месяц'],ticktext=[f'{months[d.month-1]}<br>{d.year}' for d in data['Месяц']])
    fig.update_yaxes(tickformat=',.0f')
    return chart_style(fig)


def category_chart(lines):
    data=lines.groupby('category',as_index=False).revenue.sum().sort_values('revenue',ascending=False)
    if len(data)>4:
        rest=data.iloc[4:].revenue.sum()
        data=pd.concat([data.head(4),pd.DataFrame([{'category':'Остальные категории','revenue':rest}])],ignore_index=True)
    fig=px.pie(data,names='category',values='revenue',hole=.7,color_discrete_sequence=['#34cba0','#ffd261','#ff9876','#a88cfa','#5a9aff'])
    fig.update_traces(textinfo='none',hovertemplate='%{label}: %{percent}<extra></extra>')
    fig=chart_style(fig)
    fig.update_layout(showlegend=True,legend=dict(orientation='h',y=-.12,x=.5,xanchor='center',font=dict(size=10)))
    return fig
