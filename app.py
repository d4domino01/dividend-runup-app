import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="Income Rotation Engine", layout="centered")
st.title("🔥 Ultra-Aggressive Income Rotation Engine")
st.caption("Momentum + income-weighted ETF rotation for dividend compounding")

ETF_LIST = ["CHPY", "QDTE", "XDTE", "JEPQ", "AIPI"]
MARKET = "QQQ"
WINDOW = 120

# ================================
# DATA
# ================================

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

# ================================
# MARKET MODE
# ================================

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

st.metric("QQQ (last 2h)", f"{bench_change*100:.2f}%")

# ================================
# ETF ANALYSIS
# ================================

rows = []
today = datetime.utcnow().date()

for etf in ETF_LIST:

    data = get_intraday(etf)
    if data is None:
        continue

    chg = data["Close"].iloc[-1] / data["Close"].iloc[0] - 1
    vol = data["Close"].pct_change().std()

    exdiv, dividend = get_next_exdiv(etf)
    days = (exdiv - today).days if exdiv else None

    income_score = 0
    if dividend:
        if dividend > 0.5: income_score = 3
        elif dividend > 0.2: income_score = 2
        else: income_score = 1

    score = chg*100*40 - vol*1000*8 + income_score*6

    if days is not None and 0 <= days <= 5:
        score += 10

    rows.append([
        etf, chg, vol, score, exdiv, days, dividend
    ])

df = pd.DataFrame(rows, columns=[
    "ETF","Momentum","Volatility","Score","Next Ex-Div","Days","Dividend"
]).sort_values("Score", ascending=False).reset_index(drop=True)

# ================================
# SIGNALS
# ================================

signals = []

for _, r in df.iterrows():
    if r["Days"] is not None and r["Days"] <= 2:
        sig = "HOLD (Ex-Div Soon)"
    elif mode == "RISK-OFF" and r["Momentum"] < 0:
        sig = "REDUCE"
    elif r["Score"] > 10:
        sig = "BUY"
    else:
        sig = "WAIT"
    signals.append(sig)

df["Signal"] = signals

# ================================
# DISPLAY
# ================================

st.subheader("📊 Rotation Ranking")

styled = df.style.format({
    "Momentum":"{:.2%}",
    "Volatility":"{:.4f}",
    "Dividend":"${:.2f}"
}).applymap(
    lambda x: "background-color:#b6f2c2" if x=="BUY" else
              "background-color:#f7b2b2" if x=="REDUCE" else "",
    subset=["Signal"]
)

st.dataframe(styled, use_container_width=True)

# ================================
# ACTION SUMMARY
# ================================

buys = df[df["Signal"]=="BUY"]["ETF"].tolist()
holds = df[df["Signal"].str.contains("HOLD")]["ETF"].tolist()
sells = df[df["Signal"]=="REDUCE"]["ETF"].tolist()

st.subheader("🔄 Rotation Plan")

if buys:
    st.success("🔥 Add to: " + ", ".join(buys))
if holds:
    st.info("📆 Hold for dividend: " + ", ".join(holds))
if sells:
    st.error("⬇ Reduce: " + ", ".join(sells))
if not buys and not sells:
    st.info("No strong rotation signals today.")

st.caption("Model blends momentum, volatility, dividend size, and proximity to ex-div date.")
