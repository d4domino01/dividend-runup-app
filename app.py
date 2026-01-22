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
st.caption("Weekly ETF compounding using momentum + market regime (last 120 minutes)")

# ======================================================
# SETTINGS
# ======================================================

ETF_LIST = ["CHPY", "QDTE", "XDTE", "JEPQ", "AIPI"]
MARKET = "QQQ"
WINDOW = 120  # minutes

# Ultra-Aggressive Allocation (Risk-On)
AGGRESSIVE_ALLOC = {
    "CHPY": 0.30,
    "QDTE": 0.30,
    "XDTE": 0.25,
    "JEPQ": 0.10,
    "AIPI": 0.05,
}

# Defensive Allocation (Risk-Off)
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
    st.success("📈 Market Status: OPEN — using live power-hour data")
else:
    st.info("🕒 Market Status: CLOSED — using last session close momentum")

# ======================================================
# DATA
# ======================================================

@st.cache_data(ttl=300)
def get_intraday_change(ticker):
    data = yf.download(ticker, period="2d", interval="1m", progress=False)

    if data is None or len(data) < WINDOW:
        return None, None, None

    recent = data.tail(WINDOW)
    start_price = float(recent["Close"].iloc[0])
    end_price = float(recent["Close"].iloc[-1])

    pct = (end_price - start_price) / start_price
    vol = recent["Close"].pct_change().std()

    return float(pct), float(vol), recent

# ======================================================
# MARKET REGIME
# ======================================================

bench_chg, bench_vol, _ = get_intraday_change(MARKET)

if bench_chg is None:
    st.error("Not enough intraday data available.")
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

st.metric("QQQ – Last 120 min", f"{bench_chg*100:.2f}%")

alloc = AGGRESSIVE_ALLOC if market_mode != "DEFENSIVE" else DEFENSIVE_ALLOC

# ======================================================
# CASH INPUT
# ======================================================

st.markdown("## 💵 Reinvestment Amount")
cash = st.number_input("Cash to invest today ($)", min_value=0, value=300, step=50)

# ======================================================
# ETF MOMENTUM + ALLOCATION
# ======================================================

rows = []

for etf in ETF_LIST:
    chg, vol, _ = get_intraday_change(etf)
    if chg is None:
        continue

    price_data = yf.download(etf, period="1d", interval="1m", progress=False)
    price = float(price_data["Close"].dropna().iloc[-1])

    dollars = cash * alloc[etf]
    shares = int(dollars // price)

    rows.append([
        etf,
        chg,
        vol,
        alloc[etf],
        dollars,
        shares,
        price
    ])

df = pd.DataFrame(rows, columns=[
    "ETF", "Momentum", "Volatility", "Target %", "$ Allocation", "Shares to Buy", "Price"
])

df = df.sort_values("Momentum", ascending=False).reset_index(drop=True)

# ======================================================
# SIGNALS
# ======================================================

signals = []

for i, row in df.iterrows():
    if market_mode == "DEFENSIVE":
        signal = "REDUCE" if row["Momentum"] < 0 else "WAIT"
    else:
        if i < 3:
            signal = "BUY"
        elif row["Momentum"] < -0.003:
            signal = "REDUCE"
        else:
            signal = "WAIT"
    signals.append(signal)

df["Signal"] = signals

# ======================================================
# DISPLAY TABLE
# ======================================================

st.markdown("## 📊 What To Buy This Session")

def color_signal(val):
    if val == "BUY":
        return "background-color: #b6f2c2"
    if val == "REDUCE":
        return "background-color: #f7b2b2"
    return ""

styled = df.style.format({
    "Momentum": "{:.2%}",
    "Volatility": "{:.4f}",
    "Target %": "{:.0%}",
    "$ Allocation": "${:,.0f}",
    "Price": "${:.2f}"
}).applymap(color_signal, subset=["Signal"])

st.dataframe(styled, use_container_width=True)

# ======================================================
# SIMPLE ACTION SUMMARY
# ======================================================

buys = df[df["Signal"] == "BUY"]

if len(buys) == 0:
    st.info("No strong buy signals right now. Consider waiting or defensive rotation.")
else:
    top = ", ".join(buys["ETF"].tolist())
    st.success(f"🔥 Focus buys on: {top}")

st.caption("Logic: Market regime via QQQ last 120 min + ETF momentum ranking + aggressive income weighting.")
