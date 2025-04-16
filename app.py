import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import timedelta

st.set_page_config(layout="wide")
st.title("Dividend Run-Up Strategy Backtester")

# Sidebar input options
tickers = st.sidebar.text_input("Tickers (comma-separated)", "MO, T, O, JEPI, VZ, XOM").split(',')
years_back = st.sidebar.slider("Years Back", 1, 10, 5)
buy_days = st.sidebar.number_input("Buy Days Before Ex-Div", 1, 30, 10)
sell_days = st.sidebar.number_input("Sell Days Before Ex-Div", 1, 10, 3)
starting_capital = st.sidebar.number_input("Starting Capital", 1000, 1000000, 10000)
min_trades = st.sidebar.slider("Min # of Ex-Div Events", 2, 20, 4)
min_success_rate = st.sidebar.slider("Min Success Rate (%)", 0, 100, 70)

# Clean ticker list
tickers = [t.strip().upper() for t in tickers if t.strip()]

@st.cache_data
def get_proven_tickers(tickers, buy_days, sell_days, years_back, min_trades, min_success_rate):
    valid_tickers = []

    for ticker in tickers:
        stock = yf.Ticker(ticker)
        dividends = stock.dividends
        if dividends.empty:
            continue

        dividends = dividends[dividends.index > pd.Timestamp.now() - pd.DateOffset(years=years_back)]
        returns = []

        for ex_date in dividends.index:
            ex_date = ex_date.date()
            buy_date = ex_date - timedelta(days=buy_days)
            sell_date = ex_date - timedelta(days=sell_days)

            hist = stock.history(start=buy_date - timedelta(days=2), end=sell_date + timedelta(days=2))
            if buy_date not in hist.index or sell_date not in hist.index:
                continue

            buy_price = hist.loc[buy_date]['Close']
            sell_price = hist.loc[sell_date]['Close']
            return_pct = (sell_price - buy_price) / buy_price * 100
            returns.append(return_pct)

        if len(returns) >= min_trades:
            win_rate = (sum(1 for r in returns if r > 0) / len(returns)) * 100
            if win_rate >= min_success_rate:
                valid_tickers.append(ticker)

    return valid_tickers

@st.cache_data
def simulate_strategy(valid_tickers, buy_days, sell_days, years_back, starting_capital):
    all_trades = []

    for ticker in valid_tickers:
        stock = yf.Ticker(ticker)
        dividends = stock.dividends
        if dividends.empty:
            continue

        dividends = dividends[dividends.index > pd.Timestamp.now() - pd.DateOffset(years=years_back)]

        for ex_date in dividends.index:
            ex_date = ex_date.date()
            buy_date = ex_date - timedelta(days=buy_days)
            sell_date = ex_date - timedelta(days=sell_days)

            hist = stock.history(start=buy_date - timedelta(days=2), end=sell_date + timedelta(days=2))
            if buy_date not in hist.index or sell_date not in hist.index:
                continue

            buy_price = hist.loc[buy_date]['Close']
            sell_price = hist.loc[sell_date]['Close']
            return_pct = (sell_price - buy_price) / buy_price * 100

            all_trades.append({
                "Ticker": ticker,
                "Buy Date": buy_date,
                "Sell Date": sell_date,
                "Ex-Div Date": ex_date,
                "Buy Price": round(buy_price, 2),
                "Sell Price": round(sell_price, 2),
                "Return %": round(return_pct, 2)
            })

    df = pd.DataFrame(all_trades)
    df = df.sort_values("Sell Date").reset_index(drop=True)

    portfolio = starting_capital
    history = []

    for _, row in df.iterrows():
        growth = 1 + (row["Return %"] / 100)
        portfolio *= growth
        history.append(round(portfolio, 2))

    df["Portfolio Value"] = history
    return df

# Run logic
if st.button("Run Backtest"):
    st.info("Filtering for proven tickers...")
    valid = get_proven_tickers(tickers, buy_days, sell_days, years_back, min_trades, min_success_rate)

    if not valid:
        st.error("No tickers met the proven run-up criteria.")
    else:
        st.success(f"{len(valid)} proven tickers found: {', '.join(valid)}")
        df = simulate_strategy(valid, buy_days, sell_days, years_back, starting_capital)

        st.line_chart(df.set_index("Sell Date")["Portfolio Value"])
        st.dataframe(df)

        final_value = df["Portfolio Value"].iloc[-1]
        total_return = (final_value / starting_capital - 1) * 100
        st.metric("Final Portfolio Value", f"${final_value:,.2f}", f"{total_return:.2f}%")

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download Trade History CSV", csv, "dividend_strategy.csv", "text/csv")