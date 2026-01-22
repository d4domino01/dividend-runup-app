import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time
import pytz

# ======================================================
# PAGE
# ======================================================

st.set_page_config(page_title="Income Rotation Engine", layout="centered")
st.title("🔥 Ultra-Aggressive Income Rotation Engine")
st.caption("Momentum + income-weighted ETF rotation for compounding")

# ======================================================
# SETTINGS
# ======================================================

ETF_LIST = ["CHPY", "QDTE", "XDTE", "JEPQ", "AIPI"]
MARKET = "QQQ"

FALLBACK_WINDOWS = [120, 60, 30]

# Dividend power (monthly / weekly equivalents)
INCOME_POWER = {
    "QDTE": 0.12,
    "XDTE": 0.12,
    "CHPY": 0.52,
    "JEPQ": 0.57,
    "AIPI": 1.20,
}

AGGRESSIVE_ALLOC = {
    "CHPY": 0.30,
    "QDTE": 0.30,
    "XDTE": 0.25,
    "JEPQ": 0.10,
    "AIPI": 0.05,
}

DEFENSIVE_ALLOC = {
    "CHPY": 0.10,
    "QDTE": 0.25,
    "XDTE": 0.20,
    "JEPQ": 0.25,
    "AIPI": 0.20,
}

# ======================================================
# MARKET STATUS
# ======================================================

eastern = pytz.timezone("US/Eastern")
now = datetime.now(eastern).time()

market_open = time(9, 30)
market_close = time(16, 0)
market_is_open = market_open <= now <= market_close

if market_is_open:
    st.success("📈 Market OPEN — using live intraday momentum")
else:
    st.info("🕒 Market CLOSED — using last session momentum")

# ======================================================
# DATA
# ======================================================

@st.cache_data(ttl=300)
def get_intraday_change(ticker):

    data = yf.download(ticker, period="2d", interval="1m", progress=False)

    if data is None or len(data) < 30:
        return None, None, None, None

    for win in FALLBACK_WINDOWS:
        if len(data) >= win:
            recent = data.tail(win)
            start = float(recent["Close"].iloc[0])
            end = float(recent["Close"].iloc[-1])
            pct = (end - start) / start
            vol = recent["Close"].pct_change().std()
            return pct, vol, recent, win

    return None, None, None, None

# ======================================================
# MARKET REGIME
# ======================================================

bench_chg, bench_vol, _, bench_window = get_intraday_change(MARKET)

if bench_chg is None:
    st.error("Not enough intraday data available from Yahoo.")
    st.stop()

if bench_chg > 0.003:
    market_mode = "AGGRESSIVE"
elif bench_chg < -0.003:
    market_mode = "DEFENSIVE"
else:
    market_mode = "NEUTRAL"

if market_mode == "AGGRESSIVE":
    st.success("🟢 MARKET MODE: AGGRESSIVE (risk-on)")
elif market_mode == "DEFENSIVE":
    st.error("🔴 MARKET MODE: DEFENSIVE (risk-off)")
else:
    st.warning("🟡 MARKET MODE: NEUTRAL")

st.metric(f"QQQ – Last {bench_window} min", f"{bench_chg*100:.2f}%")

alloc = AGGRESSIVE_ALLOC if market_mode != "DEFENSIVE" else DEFENSIVE_ALLOC

# ======================================================
# CASH INPUT
# ======================================================

st.markdown("## 💵 Reinvestment Amount")
cash = st.number_input("Cash to deploy today ($)", min_value=0, value=300, step=50)

# ======================================================
# ETF SCORING
# ======================================================

rows = []

max_income = max(INCOME_POWER.values())

for etf in ETF_LIST:
    chg, vol, _, used_window = get_intraday_change(etf)
    if chg is None:
        continue

    price_data = yf.download(etf, period="1d", interval="1m", progress=False)
    price = float(price_data["Close"].dropna().iloc[-1])

    income_weight = INCOME_POWER[etf] / max_income

    # Core score: momentum + income bias – volatility
    score = (chg * 100 * 40) + (income_weight * 25) - (vol * 1000 * 10)

    dollars = cash * alloc[etf]
    shares = int(dollars // price)

    rows.append([
        etf, chg, vol, income_weight, score,
        alloc[etf], dollars, shares, price, used_window
    ])

df = pd.DataFrame(rows, columns=[
    "ETF", "Momentum", "Volatility", "IncomeWeight", "Score",
    "Target %", "$ Allocation", "Shares to Buy", "Price", "Window(min)"
])

df = df.sort_values("Score", ascending=False).reset_index(drop=True)

# ======================================================
# SIGNALS (BUY / WAIT / SELL)
# ======================================================

signals = []

for i, row in df.iterrows():

    if market_mode == "DEFENSIVE":
        signal = "SELL" if row["Momentum"] < 0 else "WAIT"
    else:
        if i < 2:
            signal = "BUY"
        elif row["Momentum"] < -0.003 and i >= 3:
            signal = "SELL"
        else:
            signal = "WAIT"

    signals.append(signal)

df["Signal"] = signals

# ======================================================
# DISPLAY
# ======================================================

st.markdown("## 📊 Rotation Table")

def color_signal(val):
    if val == "BUY":
        return "background-color: #b6f2c2"
    if val == "SELL":
        return "background-color: #f7b2b2"
    return ""

styled = df.style.format({
    "Momentum": "{:.2%}",
    "Volatility": "{:.4f}",
    "IncomeWeight": "{:.2f}",
    "Score": "{:.1f}",
    "Target %": "{:.0%}",
    "$ Allocation": "${:,.0f}",
    "Price": "${:.2f}"
}).applymap(color_signal, subset=["Signal"])

st.dataframe(styled, use_container_width=True)

# ======================================================
# ACTION SUMMARY
# ======================================================

buys = df[df["Signal"] == "BUY"]["ETF"].tolist()
sells = df[df["Signal"] == "SELL"]["ETF"].tolist()

st.markdown("## ⚡ Action Plan")

if buys:
    st.success(f"✅ BUY / ADD: {', '.join(buys)}")
else:
    st.info("No strong buy setups right now.")

if sells:
    st.error(f"🔴 SELL / TRIM: {', '.join(sells)} → Rotate into leaders")
else:
    st.info("No forced sells today.")

st.caption("Scoring = Momentum + Income Bias – Volatility. Designed for aggressive dividend compounding.")
