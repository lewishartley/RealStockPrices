pip install pandas_market_calendars
import requests
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta
from pandas_market_calendars import get_calendar
import plotly.graph_objs as go

polygon_api_key = "KkfCQ7fsZnx0yK4bhX9fD81QplTh0Pf3" #This is not my API key, I have borrowed it from https://github.com/quantgalore as it seems to be a premium one
fred_api_key = "819e4a9a41b51fba83d9b4d471c12612"

st.title('Real (Inflation Adjusted) Stock Prices')

start_date = st.date_input("Start date", datetime.today())
end_date = st.date_input("End date", min_value=start_date + timedelta(days=1), max_value=datetime.today())

infoptions =["CPI", "RPI", "PCE", "PPI"]
inflation_option = st.selectbox("Inflation Measure", infoptions)

if inflation_option == "CPI":
    inflation_measure = "CPIAUCSL"
elif inflation_option == "RPI":
    inflation_measure = "RPI"
elif inflation_option == "PCE":
    inflation_measure = "PCEPI"
elif inflation_option == "PPI":
    inflation_measure = "PPICMM"

calendar = get_calendar("NYSE")
trading_dates = calendar.schedule(start_date = start_date, end_date = end_date).index.strftime("%Y-%m-%d").values #enures start/end dates are trading days & also puts them in correct format for api

ticker_input = st.text_input('Ticker symbol (e.g. AAPL)')
ticker_data = pd.json_normalize(requests.get(f"https://api.polygon.io/v2/aggs/ticker/{ticker_input}/range/1/day/{trading_dates[0]}/{trading_dates[-1]}?adjusted=true&sort=asc&limit=50000&apiKey={polygon_api_key}").json()["results"]).set_index("t")
ticker_data.index = pd.to_datetime(ticker_data.index, unit="ms", utc=True).tz_convert("America/New_York")
ticker_data.index = pd.to_datetime(ticker_data.index.date)
ticker_data = ticker_data[["c"]].dropna()
ticker_data = ticker_data.rename(columns={'c' : 'Nominal Price'})

inflation_data = pd.json_normalize(requests.get(f"https://api.stlouisfed.org/fred/series/observations?series_id={inflation_measure}&observation_start={trading_dates[0]}&observation_end={trading_dates[-1]}&api_key={fred_api_key}&file_type=json").json()["observations"]).set_index("date")
inflation_data = inflation_data[["value"]]
inflation_data["value"] = pd.to_numeric(inflation_data["value"])
inflation_data["index_relative"] = inflation_data.iloc[1:,0] / inflation_data.shift(1).iloc[:,0]
inflation_data['rebased'] = [100] + list(inflation_data['index_relative'][1:])
inflation_data['rebased'] = inflation_data['rebased'].cumprod()
inflation_data.index = pd.to_datetime(inflation_data.index)
inflation_data['year_month'] = inflation_data.index.strftime('%Y-%m')

daily_inflation = {
    'date': pd.date_range(start=trading_dates[0], end=trading_dates[-1], freq='D'),
}

daily_inflation = pd.DataFrame(daily_inflation)
daily_inflation['year_month'] = daily_inflation['date'].dt.strftime('%Y-%m')
daily_inflation = pd.merge(daily_inflation, inflation_data, on='year_month', how='left')
daily_inflation.set_index('date', inplace=True)
daily_inflation.index = pd.to_datetime(daily_inflation.index, unit="ms", utc=True).tz_convert("America/New_York")
daily_inflation.index = pd.to_datetime(daily_inflation.index.date)
daily_inflation = daily_inflation.drop(['value', 'index_relative', 'year_month'], axis=1)
daily_inflation['rebased'] = daily_inflation['rebased'].ffill()
ticker_inf = ticker_data.join(daily_inflation, how='left')
ticker_inf['rebased'] = ticker_inf['rebased']/100
ticker_inf['Real Price'] = ticker_inf['Nominal Price']/ticker_inf['rebased']

show_real = st.checkbox("Real stock price", value=True)
show_nominal = st.checkbox("Nominal stock price", value=True)

fig = go.Figure()
tracenom = go.Scatter(x=ticker_inf['Nominal Price'].index, y=ticker_inf['Nominal Price'].values, mode='lines', name='Nominal Price', line=dict(color='red'), showlegend=True)
tracerea = go.Scatter(x=ticker_inf['Real Price'].index, y=ticker_inf['Real Price'].values, mode='lines', name='Real Price', line=dict(color='blue'), showlegend=True)

if show_nominal:
    fig.add_trace(tracenom)

if show_real:
    fig.add_trace(tracerea)

fig.update_layout(
    title= ticker_input +' Real Price Chart',
    xaxis_title='Date',
    yaxis_title='Price',
    template='plotly_dark',
    title_x=0.5,
)

if show_real == True or show_nominal == True:
    st.plotly_chart(fig)

display_df = ticker_inf.drop(columns=['rebased'])
display_df.index = display_df.index.date
display_df.index.name = 'Date'
display_df = display_df.sort_index(ascending=False)
st.dataframe(display_df)
