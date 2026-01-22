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
st.caption("Momentum + income-weighted ETF rotation for dividend compounding")

# ======================================================
# SETTINGS
# ======================================================

ETF_LIST = ["CHPY", "QDTE", "XDTE", "JEPQ", "AIPI"]
MARKET = "QQQ"

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
    st.success("📈 Market OPEN — using intraday momentum")
else:
    st.info("🕒 Market CLOSED — using last sessions momentum")

# ======================================================
# DATA HELPERS
# ======================================================

@st.cache_data(ttl=300)
def get_momentum(ticker):

    try:
        intraday = yf.download(ticker, period="2d", interval="1m", progress=False)
        if intraday is not None and len(intraday) > 60:
            recent = intraday.tail(120)
            start = recent["Close"].iloc[0]
            end = recent["Close"].iloc[-1]
            pct = (end - start) / start
            vol = recent["Close"].pct_change().std()
            return float(pct), float(vol), "intraday"
    except:
        pass

    # ---- fallback to daily ----
    daily = yf.download(ticker, period="10d", interval="1d", progress=False)
    if daily is None or len(daily) < 3:
        return None, None, None

    recent = daily.tail(3)
    start = recent["Close"].iloc[0]
    end = recent["Close"].iloc[-1]
    pct = (end - start) / start
    vol = recent["Close"].pct_change().std()

    return float(pct), float(vol), "daily"


@st.cache_data(ttl=300)
def get_last_price(ticker):
    d = yf.download(ticker, period="5d", interval="1d", progress=False)
    return float(d["Close"].dropna().iloc[-1])

# ======================================================
# MARKET REGIME
# ======================================================

bench_chg, bench_vol, mode = get_momentum(MARKET)

if bench_chg is None:
    st.error("Market data unavailable from Yahoo right now.")
    st.stop()

if bench_chg > 0.003:
    market_mode = "AGGRESSIVE"
elif bench_chg < -0.003:
    market_mode = "DEFENSIVE"
else:
    market_mode = "NEUTRAL"

if market_mode == "AGGRESSIVE":
    st.success("🟢 MARKET MODE: AGGRESSIVE")
elif market_mode == "DEFENSIVE":
    st.error("🔴 MARKET MODE: DEFENSIVE")
else:
    st.warning("🟡 MARKET MODE: NEUTRAL")

st.metric("Market Momentum (QQQ)", f"{bench_chg*100:.2f}%")

alloc = AGGRESSIVE_ALLOC if market_mode != "DEFENSIVE" else DEFENSIVE_ALLOC

# ======================================================
# PORTFOLIO INPUT
# ======================================================

st.markdown("## 📦 Your Current Holdings")

portfolio = {}
cols = st.columns(len(ETF_LIST))

for i, etf in enumerate(ETF_LIST):
    portfolio[etf] = cols[i].number_input(f"{etf} shares", min_value=0, value=0, step=1)

# ======================================================
# ETF SCORING
# ======================================================

rows = []
max_income = max(INCOME_POWER.values())

for etf in ETF_LIST:

    chg, vol, src = get_momentum(etf)
    if chg is None:
        continue

    price = get_last_price(etf)
    income_weight = INCOME_POWER[etf] / max_income

    score = (chg * 100 * 40) + (income_weight * 25) - (vol * 1000 * 10)

    rows.append([
        etf, chg, vol, income_weight, score,
        alloc[etf], price, src
    ])

df = pd.DataFrame(rows, columns=[
    "ETF", "Momentum", "Volatility", "IncomeWeight", "Score",
    "Target %", "Price", "DataSource"
])

df = df.sort_values("Score", ascending=False).reset_index(drop=True)

# ======================================================
# SIGNALS
# ======================================================

signals = []

for i, row in df.iterrows():
    if market_mode == "DEFENSIVE":
        signal = "SELL" if row["Momentum"] < 0 else "WAIT"
    else:
        if i < 2:
            signal = "BUY"
        elif row["Momentum"] < -0.003:
            signal = "SELL"
        else:
            signal = "WAIT"
    signals.append(signal)

df["Signal"] = signals

# ======================================================
# INCOME DASHBOARD
# ======================================================

income_rows = []
total_monthly = 0

for etf in ETF_LIST:
    shares = portfolio.get(etf, 0)
    monthly = shares * INCOME_POWER[etf]
    total_monthly += monthly
    income_rows.append([etf, shares, monthly])

income_df = pd.DataFrame(income_rows, columns=["ETF", "Shares", "Monthly Income $"])
weekly_income = total_monthly / 4.3

# ======================================================
# DISPLAY
# ======================================================

st.markdown("## 📊 Rotation Signals")

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
    "Price": "${:.2f}"
}).applymap(color_signal, subset=["Signal"])

st.dataframe(styled, use_container_width=True)

# ======================================================
# ACTION SUMMARY
# ======================================================

st.markdown("## ⚡ Action Plan")

buys = df[df["Signal"] == "BUY"]["ETF"].tolist()
sells = df[df["Signal"] == "SELL"]["ETF"].tolist()

if buys:
    st.success(f"✅ BUY / ADD: {', '.join(buys)}")
else:
    st.info("No strong buys right now.")

if sells:
    st.error(f"🔴 SELL / TRIM: {', '.join(sells)} → rotate into leaders")
else:
    st.info("No forced sells today.")

# ======================================================
# INCOME TRACKER
# ======================================================

st.markdown("## 💰 Income Tracker")

col1, col2, col3 = st.columns(3)
col1.metric("Monthly Income", f"${total_monthly:,.2f}")
col2.metric("Weekly Income", f"${weekly_income:,.2f}")
col3.metric("Target Progress", f"{(total_monthly/1000)*100:.1f}%")

st.dataframe(income_df)

st.caption("Goal: $1,000/month dividend income — aggressive rotation to reach it faster.")
