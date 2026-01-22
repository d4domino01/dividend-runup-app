import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Income Rotation Engine", layout="centered")
st.title("🔥 Ultra-Aggressive Income Rotation Engine")
st.caption("Weekly ETF compounding using momentum + market regime")

# ======================================================
# SETTINGS
# ======================================================

ETF_LIST = ["CHPY", "QDTE", "XDTE", "JEPQ", "AIPI"]
MARKET = "QQQ"
WINDOW = 120  # minutes

# Dividend per share
DIVIDENDS = {
    "QDTE": {"amount": 0.12, "freq": "weekly"},
    "XDTE": {"amount": 0.12, "freq": "weekly"},
    "CHPY": {"amount": 0.52, "freq": "weekly"},
    "JEPQ": {"amount": 0.57, "freq": "monthly"},
    "AIPI": {"amount": 1.20, "freq": "monthly"},
}

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
# HELPERS
# ======================================================

@st.cache_data(ttl=300)
def get_intraday_change(ticker):
    data = yf.download(ticker, period="1d", interval="1m", progress=False)
    if data is None or len(data) < WINDOW:
        return None, None

    recent = data.tail(WINDOW)
    start_price = float(recent["Close"].iloc[0])
    end_price = float(recent["Close"].iloc[-1])
    pct = (end_price - start_price) / start_price
    vol = recent["Close"].pct_change().std()

    return float(pct), float(vol)

@st.cache_data(ttl=300)
def get_price(ticker):
    data = yf.download(ticker, period="1d", interval="1m", progress=False)
    if len(data) == 0:
        return None
    return float(data["Close"].iloc[-1])

def monthly_income_per_share(ticker):
    d = DIVIDENDS[ticker]
    if d["freq"] == "weekly":
        return d["amount"] * 4.33
    else:
        return d["amount"]

# ======================================================
# MARKET REGIME
# ======================================================

bench_chg, _ = get_intraday_change(MARKET)

if bench_chg is None:
    st.warning("Market data not available yet. Try later in the session.")
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
# CURRENT HOLDINGS INPUT
# ======================================================

st.markdown("## 📦 Your Current Shares")

holdings = {}
cols = st.columns(len(ETF_LIST))

for i, etf in enumerate(ETF_LIST):
    with cols[i]:
        holdings[etf] = st.number_input(etf, min_value=0, value=0, step=1)

# ======================================================
# CURRENT INCOME
# ======================================================

monthly_income = 0
weekly_income = 0

for etf, shares in holdings.items():
    m = monthly_income_per_share(etf) * shares
    monthly_income += m
    if DIVIDENDS[etf]["freq"] == "weekly":
        weekly_income += DIVIDENDS[etf]["amount"] * shares

annual_income = monthly_income * 12

st.markdown("## 💵 Current Income")

c1, c2, c3 = st.columns(3)
c1.metric("Weekly", f"${weekly_income:,.2f}")
c2.metric("Monthly", f"${monthly_income:,.2f}")
c3.metric("Annual", f"${annual_income:,.0f}")

# ======================================================
# REINVESTMENT
# ======================================================

st.markdown("## 💵 Reinvestment Amount")
cash = st.number_input("Cash to invest today ($)", min_value=0, value=300, step=50)

rows = []
new_monthly_income = monthly_income

for etf in ETF_LIST:
    chg, vol = get_intraday_change(etf)
    price = get_price(etf)

    if chg is None or price is None:
        continue

    dollars = cash * alloc[etf]
    shares_to_buy = int(dollars // price)

    inc = monthly_income_per_share(etf) * shares_to_buy
    new_monthly_income += inc

    rows.append([
        etf,
        chg,
        alloc[etf],
        dollars,
        shares_to_buy,
        price,
        inc
    ])

df = pd.DataFrame(rows, columns=[
    "ETF", "Momentum", "Target %", "$ Allocation", "Shares to Buy", "Price", "Monthly Income +"
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
# DISPLAY
# ======================================================

st.markdown("## 📊 What To Buy This Week")

def color_signal(val):
    if val == "BUY":
        return "background-color: #b6f2c2"
    if val == "REDUCE":
        return "background-color: #f7b2b2"
    return ""

styled = df.style.format({
    "Momentum": "{:.2%}",
    "Target %": "{:.0%}",
    "$ Allocation": "${:,.0f}",
    "Price": "${:.2f}",
    "Monthly Income +": "${:.2f}"
}).applymap(color_signal, subset=["Signal"])

st.dataframe(styled, use_container_width=True)

# ======================================================
# INCOME PROJECTION
# ======================================================

st.markdown("## 🎯 Income After This Reinvestment")

increase = new_monthly_income - monthly_income

p1, p2, p3 = st.columns(3)
p1.metric("New Monthly Income", f"${new_monthly_income:,.2f}", f"+${increase:,.2f}")
p2.metric("Months to $500/mo", f"{max(0, int((500 - new_monthly_income) / max(increase,1)))}")
p3.metric("Months to $1,000/mo", f"{max(0, int((1000 - new_monthly_income) / max(increase,1)))}")

st.caption("Projection assumes similar reinvestment size and dividend stability.")

