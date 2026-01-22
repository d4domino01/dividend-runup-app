import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# ======================================================
# PAGE
# ======================================================

st.set_page_config(page_title="Income Trading Cockpit", layout="centered")
st.title("🔥 Dividend Income Trading Cockpit")
st.caption("Momentum + ex-div timing + income acceleration toward $1,000/month")

ETF_LIST = ["QDTE", "XDTE", "CHPY", "AIPI", "JEPQ"]
MARKET = "QQQ"
WINDOW = 120
TARGET_INCOME = 1000

# ======================================================
# YOUR HOLDINGS (PRE-FILLED)
# ======================================================

st.subheader("📥 Your Portfolio")

DEFAULT_HOLDINGS = {
    "QDTE": 110,
    "XDTE": 69,
    "CHPY": 55,
    "AIPI": 14,
    "JEPQ": 19,
}

holdings = {}
for etf in ETF_LIST:
    holdings[etf] = st.number_input(f"{etf} Shares", min_value=0, value=DEFAULT_HOLDINGS[etf], step=1)

cash_balance = st.number_input("💵 Available Cash ($)", min_value=0.0, value=0.0, step=50.0)

# ======================================================
# DATA
# ======================================================

@st.cache_data(ttl=300)
def get_intraday(ticker):
    df = yf.download(ticker, period="1d", interval="1m", progress=False)
    if df is None or len(df) < WINDOW:
        return None
    return df.tail(WINDOW)

@st.cache_data(ttl=3600)
def get_next_exdiv(ticker):
    try:
        url = f"https://financialmodelingprep.com/api/v3/historical-price-full/stock_dividend/{ticker}?apikey=demo"
        r = requests.get(url, timeout=10).json()
        divs = r.get("historical", [])
        today = datetime.utcnow().date()
        for d in divs:
            ex = datetime.strptime(d["date"], "%Y-%m-%d").date()
            if ex >= today:
                return ex, float(d["dividend"])
    except:
        pass
    return None, None

# ======================================================
# MARKET MODE
# ======================================================

bench = get_intraday(MARKET)
if bench is None:
    st.warning("Market data not available yet.")
    st.stop()

bench_change = bench["Close"].iloc[-1] / bench["Close"].iloc[0] - 1

if bench_change > 0.003:
    mode = "RISK-ON"
elif bench_change < -0.003:
    mode = "RISK-OFF"
else:
    mode = "NEUTRAL"

if mode == "RISK-ON":
    st.success("🟢 MARKET MODE: RISK-ON")
elif mode == "RISK-OFF":
    st.error("🔴 MARKET MODE: RISK-OFF")
else:
    st.warning("🟡 MARKET MODE: NEUTRAL")

st.metric("QQQ (last 120 min)", f"{bench_change*100:.2f}%")

# ======================================================
# ETF ANALYSIS
# ======================================================

rows = []
today = datetime.utcnow().date()

portfolio_value = 0
monthly_income_now = 0

for etf in ETF_LIST:

    data = get_intraday(etf)
    if data is None:
        continue

    chg = data["Close"].iloc[-1] / data["Close"].iloc[0] - 1
    vol = data["Close"].pct_change().std()
    price = float(data["Close"].iloc[-1])

    exdiv, dividend = get_next_exdiv(etf)
    days = (exdiv - today).days if exdiv else None

    shares = holdings[etf]
    value = shares * price
    portfolio_value += value
    if dividend:
        monthly_income_now += shares * dividend

    income_score = 0
    if dividend:
        if dividend > 0.8: income_score = 3
        elif dividend > 0.4: income_score = 2
        else: income_score = 1

    score = chg*100*40 - vol*1000*8 + income_score*10
    if days is not None and 0 <= days <= 5:
        score += 12

    rows.append([
        etf, shares, price, value, dividend, exdiv, days,
        chg, vol, score, data
    ])

df = pd.DataFrame(rows, columns=[
    "ETF","Shares","Price","Value","Dividend","Next Ex-Div","Days",
    "Momentum","Volatility","Score","Chart"
]).sort_values("Score", ascending=False).reset_index(drop=True)

# ======================================================
# ROTATION ENGINE
# ======================================================

top_etf = df.iloc[0]["ETF"]
rotation_cash = cash_balance
sell_orders = []

signals = []

for _, r in df.iterrows():
    etf = r["ETF"]

    if r["Days"] is not None and r["Days"] <= 2:
        sig = "HOLD (Ex-Div Soon)"
    elif mode == "RISK-OFF" and r["Momentum"] < 0:
        sig = "REDUCE"
    elif r["Score"] < df.iloc[0]["Score"] * 0.6 and r["Shares"] > 0:
        sig = f"ROTATE → {top_etf}"
        sell_value = r["Shares"] * r["Price"]
        rotation_cash += sell_value
        sell_orders.append([etf, r["Shares"], sell_value])
    elif etf == top_etf:
        sig = "BUY / ADD"
    else:
        sig = "HOLD"

    signals.append(sig)

df["Signal"] = signals

top_price = df[df["ETF"] == top_etf]["Price"].iloc[0]
buy_shares = int(rotation_cash // top_price)
buy_cost = buy_shares * top_price

# ======================================================
# DISPLAY
# ======================================================

st.subheader("📊 Portfolio Rotation Table")

styled = df.style.format({
    "Price":"${:.2f}",
    "Value":"${:,.0f}",
    "Dividend":"${:.2f}",
    "Momentum":"{:.2%}",
    "Score":"{:.1f}"
}).applymap(
    lambda x: "background-color:#b6f2c2" if "BUY" in str(x) else
              "background-color:#f7b2b2" if "ROTATE" in str(x) or "REDUCE" in str(x) else "",
    subset=["Signal"]
)

st.dataframe(styled, use_container_width=True)

# ======================================================
# TRADE PLAN
# ======================================================

st.subheader("🔄 Suggested Trades")

if sell_orders:
    st.markdown("### ❌ Sell")
    st.dataframe(pd.DataFrame(sell_orders, columns=["ETF","Shares","Value $"]))

if buy_shares > 0:
    st.markdown("### ✅ Buy")
    st.success(f"Buy **{buy_shares} shares of {top_etf}** ≈ ${buy_cost:,.0f}")

if not sell_orders and buy_shares == 0:
    st.info("No rotation required today.")

# ======================================================
# INCOME TRACKING
# ======================================================

income_after = monthly_income_now - sum(
    s[1] * df[df["ETF"]==s[0]]["Dividend"].iloc[0] for s in sell_orders if df[df["ETF"]==s[0]]["Dividend"].iloc[0]
) + buy_shares * df[df["ETF"]==top_etf]["Dividend"].iloc[0]

st.subheader("💰 Income Progress")

col1, col2, col3 = st.columns(3)
col1.metric("Monthly Income Now", f"${monthly_income_now:,.2f}")
col2.metric("After Rotation", f"${income_after:,.2f}")
col3.metric("To $1,000 Goal", f"${TARGET_INCOME-income_after:,.2f}")

st.progress(min(income_after / TARGET_INCOME, 1.0))

# ======================================================
# CHARTS
# ======================================================

st.subheader("📈 Last 120-Min % Move")

for _, r in df.iterrows():
    base = r["Chart"]["Close"].iloc[0]
    pct = (r["Chart"]["Close"] / base - 1) * 100
    st.line_chart(pct, height=120)

# ======================================================
# SUMMARY
# ======================================================

st.info(
    f"Top target: **{top_etf}** | "
    f"Market: **{mode}** | "
    f"Rotation cash: **${rotation_cash:,.0f}**"
)

st.caption("Engine blends momentum, dividend timing, and income acceleration toward $1,000/month.")
