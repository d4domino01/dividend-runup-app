import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import timedelta

st.set_page_config(layout="centered")
st.title("📈 Dividend Run-Up Strategy Backtester")

# ---------------- USER INPUT ---------------- #

tickers_input = st.text_input("Enter Tickers (comma-separated)", "MO, T, O, XOM")
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

buy_days = st.slider("Buy Days Before Ex-Dividend", 1, 30, 10)
sell_days = st.slider("Sell Days Before Ex-Dividend", 0, 10, 3)
years_back = st.slider("Years Back", 1, 10, 5)

include_dividend = st.checkbox("Include Dividend in Return", value=True)

# ---------------- HELPERS ---------------- #

def nearest_trading_day(date, price_index):
    if date in price_index:
        return date
    earlier = price_index[price_index <= date]
    if len(earlier) == 0:
        return None
    return earlier[-1]

# ---------------- BACKTEST ---------------- #

if st.button("🚀 Run Backtest"):

    results = []

    for ticker in tickers:

        stock = yf.Ticker(ticker)
        divs = stock.dividends

        if divs.empty:
            continue

        divs = divs[divs.index > pd.Timestamp.now() - pd.DateOffset(years=years_back)]

        start = divs.index.min() - timedelta(days=buy_days + 10)
        end = divs.index.max() + timedelta(days=5)

        history = stock.history(start=start, end=end)

        if history.empty:
            continue

        for ex_date, dividend in divs.items():

            buy_date_raw = ex_date - timedelta(days=buy_days)
            sell_date_raw = ex_date - timedelta(days=sell_days)

            buy_date = nearest_trading_day(buy_date_raw, history.index)
            sell_date = nearest_trading_day(sell_date_raw, history.index)

            if buy_date is None or sell_date is None:
                continue

            buy_price = history.loc[buy_date]["Close"]
            sell_price = history.loc[sell_date]["Close"]

            price_return = (sell_price - buy_price) / buy_price

            if include_dividend:
                total_return = (sell_price + dividend - buy_price) / buy_price
            else:
                total_return = price_return

            results.append({
                "Ticker": ticker,
                "Buy Date": buy_date.date(),
                "Sell Date": sell_date.date(),
                "Dividend": round(dividend, 3),
                "Price Return %": round(price_return * 100, 2),
                "Total Return %": round(total_return * 100, 2)
            })

    df = pd.DataFrame(results)

    if df.empty:
        st.warning("No trades found. Try different settings or tickers.")
        st.stop()

    # ---------------- STATS ---------------- #

    wins = df[df["Total Return %"] > 0]
    win_rate = len(wins) / len(df) * 100
    avg_return = df["Total Return %"].mean()
    median_return = df["Total Return %"].median()

    st.success(f"✅ {len(df)} Trades Found")

    col1, col2, col3 = st.columns(3)
    col1.metric("Win Rate", f"{win_rate:.1f}%")
    col2.metric("Avg Return", f"{avg_return:.2f}%")
    col3.metric("Median Return", f"{median_return:.2f}%")

    # ---------------- EQUITY CURVE ---------------- #

    df_sorted = df.sort_values("Buy Date")
    equity = (1 + df_sorted["Total Return %"] / 100).cumprod()

    st.subheader("📊 Strategy Equity Curve")
    st.line_chart(equity)

    # ---------------- PER TICKER SUMMARY ---------------- #

    summary = df.groupby("Ticker").agg(
        Trades=("Total Return %", "count"),
        WinRate=("Total Return %", lambda x: (x > 0).mean() * 100),
        AvgReturn=("Total Return %", "mean")
    ).round(2)

    st.subheader("📌 Per-Ticker Performance")
    st.dataframe(summary)

    # ---------------- TRADE LIST ---------------- #

    st.subheader("📄 Trade Log")
    st.dataframe(df)

    # ---------------- DOWNLOAD ---------------- #

    st.download_button(
        "⬇ Download CSV",
        df.to_csv(index=False),
        "dividend_runup_results.csv",
        "text/csv"
    )
