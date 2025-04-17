import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import timedelta

st.title("Dividend Run-Up Strategy Backtester")

tickers_input = st.text_input("Enter Tickers (comma-separated)", "MO, T, O, XOM")
tickers = [ticker.strip().upper() for ticker in tickers_input.split(',') if ticker.strip()]
buy_days = st.slider("Buy Days Before Ex-Div", 1, 30, 10)
sell_days = st.slider("Sell Days Before Ex-Div", 1, 10, 3)
years_back = st.slider("Years Back", 1, 10, 5)

if st.button("Run Backtest"):
    results = []

    for ticker in tickers:
        stock = yf.Ticker(ticker)
        divs = stock.dividends
        if divs.empty:
            continue
        divs = divs[divs.index > pd.Timestamp.now() - pd.DateOffset(years=years_back)]
        history = stock.history(start=divs.index.min() - timedelta(days=buy_days + 5), end=divs.index.max())

        for ex_date in divs.index:
            buy_date = ex_date - timedelta(days=buy_days)
            sell_date = ex_date - timedelta(days=sell_days)

            if buy_date not in history.index or sell_date not in history.index:
                continue

            buy_price = history.loc[buy_date]["Close"]
            sell_price = history.loc[sell_date]["Close"]
            pct_return = (sell_price - buy_price) / buy_price * 100

            results.append({
                "Ticker": ticker,
                "Buy Date": buy_date.date(),
                "Sell Date": sell_date.date(),
                "Return %": round(pct_return, 2)
            })

    df = pd.DataFrame(results)
    if df.empty:
        st.warning("No trades found. Try different settings or tickers.")
    else:
        st.success(f"{len(df)} trades found.")
        st.dataframe(df)
        st.line_chart(df["Return %"].rolling(5).mean())
        st.download_button("Download CSV", df.to_csv(index=False), "runup_results.csv", "text/csv")