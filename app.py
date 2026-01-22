import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import timedelta
import numpy as np

st.set_page_config(layout="centered")
st.title("🔥 Income & Dividend Strategy Engine")

# ======================================================
# MARKET REGIME DETECTION (OPTION 1)
# ======================================================

WINDOW = 120
MARKET = "QQQ"

def get_intraday_change(ticker):
    data = yf.download(ticker, period="1d", interval="1m", progress=False)
    if data is None or len(data) < WINDOW:
        return None
    recent = data.tail(WINDOW)
    start = recent["Close"].iloc[0]
    end = recent["Close"].iloc[-1]
    return (end - start) / start

market_chg = get_intraday_change(MARKET)

if market_chg is None:
    st.warning("Market data not available yet.")
    market_mode = "NEUTRAL"
else:
    if market_chg > 0.003:
        market_mode = "AGGRESSIVE"
    elif market_chg < -0.003:
        market_mode = "DEFENSIVE"
    else:
        market_mode = "NEUTRAL"

if market_mode == "AGGRESSIVE":
    st.success("🟢 MARKET MODE: AGGRESSIVE (risk-on)")
elif market_mode == "DEFENSIVE":
    st.error("🔴 MARKET MODE: DEFENSIVE (risk-off)")
else:
    st.warning("🟡 MARKET MODE: NEUTRAL")

if market_chg is not None:
    st.metric("QQQ (Last 2h)", f"{market_chg*100:.2f}%")

# ======================================================
# ETF ROTATION ENGINE (INCOME ACCELERATOR)
# ======================================================

st.markdown("## 💰 ETF Income Rotation Engine")

ETF_LIST = ["QDTE", "XDTE", "CHPY", "JEPQ", "AIPI"]

AGGRESSIVE_ALLOC = {
    "QDTE": 0.38,
    "XDTE": 0.28,
    "CHPY": 0.22,
    "JEPQ": 0.07,
    "AIPI": 0.05,
}

DEFENSIVE_ALLOC = {
    "QDTE": 0.25,
    "XDTE": 0.20,
    "CHPY": 0.10,
    "JEPQ": 0.25,
    "AIPI": 0.20,
}

alloc = AGGRESSIVE_ALLOC if market_mode != "DEFENSIVE" else DEFENSIVE_ALLOC

cash = st.number_input("💵 Cash to Invest Today ($)", value=500, step=100)

rows = []

for etf in ETF_LIST:
    price_data = yf.download(etf, period="1d", interval="1m", progress=False)
    if len(price_data) == 0:
        continue
    price = price_data["Close"].iloc[-1]
    dollars = cash * alloc[etf]
    shares = int(dollars // price)
    rows.append([etf, alloc[etf]*100, round(dollars,2), shares, round(price,2)])

df_alloc = pd.DataFrame(rows, columns=["ETF","Target %","$ Allocation","Shares","Price"])

st.dataframe(df_alloc)

# ======================================================
# DIVIDEND RUN-UP OPTIMIZER (WITH MARKET FILTER)
# ======================================================

st.markdown("## 📈 Dividend Run-Up Strategy Optimizer")

tickers_input = st.text_input("Tickers (comma-separated)", "MO, T, O, XOM")
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

years_back = st.slider("Years Back", 1, 10, 5)
start_capital = st.number_input("Starting Capital ($)", value=10500, step=500)

buy_range = st.slider("Buy Days Before Ex-Dividend", 1, 30, (7, 14))
sell_range = st.slider("Sell Days Before Ex-Dividend", 0, 10, (1, 5))

def nearest_trading_day(date, price_index):
    if date in price_index:
        return date
    earlier = price_index[price_index <= date]
    if len(earlier) == 0:
        return None
    return earlier[-1]

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

            ret = (sell_price + dividend - buy_price) / buy_price

            # -------- MARKET FILTER --------
            if market_mode == "DEFENSIVE" and ret < 0:
                continue

            results.append({
                "Ticker": ticker,
                "Buy Date": buy_date,
                "Return": ret
            })

    if len(results) == 0:
        return None

    df = pd.DataFrame(results).sort_values("Buy Date")
    df["Equity"] = (1 + df["Return"]).cumprod()
    return df


if st.button("🔥 Run Optimization"):

    best = None
    best_params = None
    summary_rows = []

    for buy in range(buy_range[0], buy_range[1]+1):
        for sell in range(sell_range[0], sell_range[1]+1):

            if sell >= buy:
                continue

            df = run_strategy(buy, sell)
            if df is None:
                continue

            final_eq = df["Equity"].iloc[-1]
            total_ret = final_eq - 1

            summary_rows.append([buy, sell, total_ret])

            if best is None or total_ret > best:
                best = total_ret
                best_params = (buy, sell)
                best_df = df.copy()

    if best_params is None:
        st.warning("No valid trades found.")
        st.stop()

    opt = pd.DataFrame(summary_rows, columns=["Buy Days","Sell Days","Total Return"])
    opt = opt.sort_values("Total Return", ascending=False)

    st.success(f"🏆 Best Strategy: Buy {best_params[0]}d / Sell {best_params[1]}d before Ex-Div")

    st.subheader("📊 Top Parameter Results")
    st.dataframe(opt.head(10).style.format({"Total Return":"{:.2%}"}))

    capital_curve = start_capital * best_df["Equity"]

    st.subheader("💰 Capital Growth")
    st.line_chart(capital_curve)

    final_cap = capital_curve.iloc[-1]
    cagr = (final_cap / start_capital) ** (1 / years_back) - 1
    drawdown = (capital_curve / capital_curve.cummax() - 1).min()

    c1,c2,c3 = st.columns(3)
    c1.metric("Final Capital", f"${final_cap:,.0f}")
    c2.metric("CAGR", f"{cagr*100:.1f}%")
    c3.metric("Max Drawdown", f"{drawdown*100:.1f}%")

    st.subheader("📄 Trade Log (Best Strategy)")
    trades = best_df.copy()
    trades["Return %"] = trades["Return"] * 100
    st.dataframe(trades[["Ticker","Buy Date","Return %"]].round(2))

    st.download_button(
        "⬇ Download Trades",
        trades.to_csv(index=False),
        "runup_trades.csv",
        "text/csv"
    )
