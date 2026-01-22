import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import timedelta
import numpy as np

st.set_page_config(layout="centered")
st.title("🚀 Dividend Run-Up Strategy Optimizer")

# ---------------- USER INPUT ---------------- #

tickers_input = st.text_input("Tickers (comma-separated)", "MO, T, O, XOM")
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

years_back = st.slider("Years Back", 1, 10, 5)

start_capital = st.number_input("Starting Capital ($)", value=10500, step=500)

include_dividend = st.checkbox("Include Dividend in Return", value=True)

st.markdown("### 🔍 Optimization Ranges")

buy_range = st.slider("Buy Days Before Ex-Dividend (range)", 1, 30, (7, 14))
sell_range = st.slider("Sell Days Before Ex-Dividend (range)", 0, 10, (1, 5))

# ---------------- HELPERS ---------------- #

def nearest_trading_day(date, price_index):
    if date in price_index:
        return date
    earlier = price_index[price_index <= date]
    if len(earlier) == 0:
        return None
    return earlier[-1]

# ---------------- BACKTEST CORE ---------------- #

def run_strategy(buy_days, sell_days):

    results = []

    for ticker in tickers:

        stock = yf.Ticker(ticker)
        divs = stock.dividends

        if divs.empty:
            continue

        divs = divs[divs.index > pd.Timestamp.now() - pd.DateOffset(years=years_back)]

        start = divs.index.min() - timedelta(days=buy_days + 15)
        end = divs.index.max() + timedelta(days=5)

        history = stock.history(start=start, end=end)
        if history.empty:
            continue

        for ex_date, dividend in divs.items():

            buy_raw = ex_date - timedelta(days=buy_days)
            sell_raw = ex_date - timedelta(days=sell_days)

            buy_date = nearest_trading_day(buy_raw, history.index)
            sell_date = nearest_trading_day(sell_raw, history.index)

            if buy_date is None or sell_date is None:
                continue

            buy_price = history.loc[buy_date]["Close"]
            sell_price = history.loc[sell_date]["Close"]

            price_ret = (sell_price - buy_price) / buy_price

            if include_dividend:
                total_ret = (sell_price + dividend - buy_price) / buy_price
            else:
                total_ret = price_ret

            results.append({
                "Ticker": ticker,
                "Buy Date": buy_date,
                "Return": total_ret
            })

    if len(results) == 0:
        return None

    df = pd.DataFrame(results).sort_values("Buy Date")
    df["Equity"] = (1 + df["Return"]).cumprod()

    return df


# ---------------- OPTIMIZATION ---------------- #

if st.button("🔥 Run Optimization"):

    best = None
    best_params = None
    summary_rows = []

    for buy in range(buy_range[0], buy_range[1] + 1):
        for sell in range(sell_range[0], sell_range[1] + 1):

            if sell >= buy:
                continue

            df = run_strategy(buy, sell)
            if df is None:
                continue

            final_equity = df["Equity"].iloc[-1]
            total_return = final_equity - 1

            summary_rows.append([buy, sell, total_return])

            if best is None or total_return > best:
                best = total_return
                best_params = (buy, sell)
                best_df = df.copy()

    if best_params is None:
        st.warning("No valid trades found.")
        st.stop()

    opt = pd.DataFrame(summary_rows, columns=["Buy Days", "Sell Days", "Total Return"])
    opt = opt.sort_values("Total Return", ascending=False)

    # ---------------- RESULTS ---------------- #

    st.success(f"🏆 Best Strategy: Buy {best_params[0]} days before, Sell {best_params[1]} days before")

    st.subheader("📊 Optimization Results (Top 10)")
    st.dataframe(opt.head(10).style.format({"Total Return": "{:.2%}"}))

    # ---------------- CAPITAL GROWTH ---------------- #

    capital_curve = start_capital * best_df["Equity"]

    st.subheader("💰 Capital Growth Simulation")
    st.line_chart(capital_curve)

    final_capital = capital_curve.iloc[-1]

    years = years_back
    cagr = (final_capital / start_capital) ** (1 / years) - 1

    drawdown = (capital_curve / capital_curve.cummax() - 1).min()

    col1, col2, col3 = st.columns(3)
    col1.metric("Final Capital", f"${final_capital:,.0f}")
    col2.metric("CAGR", f"{cagr*100:.1f}%")
    col3.metric("Max Drawdown", f"{drawdown*100:.1f}%")

    # ---------------- BUY & HOLD COMPARISON ---------------- #

    st.subheader("📉 Buy & Hold Comparison")

    bh_returns = []

    for ticker in tickers:
        data = yf.download(ticker, period=f"{years_back}y", progress=False)
        if len(data) == 0:
            continue
        bh = data["Close"].iloc[-1] / data["Close"].iloc[0] - 1
        bh_returns.append(bh)

    if bh_returns:
        bh_avg = np.mean(bh_returns)
        st.metric("Avg Buy & Hold Return", f"{bh_avg*100:.1f}%")

    # ---------------- TRADE DETAILS ---------------- #

    st.subheader("📄 Trade Log (Best Strategy)")
    trades = best_df.copy()
    trades["Return %"] = trades["Return"] * 100
    st.dataframe(trades[["Ticker", "Buy Date", "Return %"]].round(2))

    st.download_button(
        "⬇ Download Trade Log",
        trades.to_csv(index=False),
        "dividend_runup_optimized_trades.csv",
        "text/csv"
    )
