import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Income Rotation Engine", layout="centered")

st.title("🔥 Ultra-Aggressive Income Rotation Engine")
st.caption("Momentum + income-weighted ETF rotation for dividend compounding")

ETF_LIST = ["QDTE", "XDTE", "CHPY", "AIPI", "JEPQ"]
MARKET = "QQQ"
WINDOW = 120

# ==============================
# HOLDINGS INPUT — MAIN PAGE
# ==============================

st.markdown("## 📥 Enter Your Current Holdings (Shares)")

col1, col2, col3 = st.columns(3)

with col1:
    qdte_sh = st.number_input("QDTE Shares", value=110, step=1)
    xdte_sh = st.number_input("XDTE Shares", value=69, step=1)

with col2:
    chpy_sh = st.number_input("CHPY Shares", value=55, step=1)
    aipi_sh = st.number_input("AIPI Shares", value=14, step=1)

with col3:
    jepq_sh = st.number_input("JEPQ Shares", value=19, step=1)

holdings = {
    "QDTE": qdte_sh,
    "XDTE": xdte_sh,
    "CHPY": chpy_sh,
    "AIPI": aipi_sh,
    "JEPQ": jepq_sh,
}

cash_to_reinvest = st.number_input("💵 Cash to deploy today ($)", value=300, step=50)

st.markdown("---")

# ==============================
# DATA
# ==============================

@st.cache_data(ttl=300)
def get_intraday(ticker):
    data = yf.download(ticker, period="1d", interval="1m", progress=False)
    if data is None or len(data) < WINDOW:
        return None, None, None, None

    recent = data.tail(WINDOW)
    start = recent["Close"].iloc[0]
    end = recent["Close"].iloc[-1]
    pct = (end - start) / start
    vol = recent["Close"].pct_change().std()
    price = recent["Close"].iloc[-1]

    return float(pct), float(vol), float(price), recent

# ==============================
# MARKET MODE
# ==============================

bench_chg, _, _, _ = get_intraday(MARKET)

if bench_chg is None:
    st.warning("Market data not available yet. Try during market hours.")
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
    st.warning("🟡 MARKET MODE: NEUTRAL — no strong edge")

st.metric("QQQ (last 120 min)", f"{bench_chg*100:.2f}%")

# ==============================
# ETF ANALYSIS
# ==============================

rows = []
total_value = 0

income_weight = {
    "QDTE": 0.6,
    "XDTE": 0.6,
    "CHPY": 1.0,
    "AIPI": 1.1,
    "JEPQ": 0.8
}

for etf in ETF_LIST:
    chg, vol, price, _ = get_intraday(etf)
    if chg is None:
        continue

    shares = holdings[etf]
    value = shares * price
    total_value += value

    score = chg*100*40 + income_weight[etf]*10 - vol*1000*5

    rows.append([etf, chg, vol, price, shares, value, score])

df = pd.DataFrame(rows, columns=[
    "ETF", "Momentum", "Volatility", "Price", "Shares", "Value", "Score"
])

df["Weight"] = df["Value"] / total_value
df = df.sort_values("Score", ascending=False).reset_index(drop=True)

# ==============================
# SIGNALS
# ==============================

signals = []
for i, row in df.iterrows():
    if market_mode == "DEFENSIVE":
        signal = "REDUCE" if row["Momentum"] < 0 else "HOLD"
    else:
        if i < 2:
            signal = "BUY"
        elif row["Momentum"] < -0.003:
            signal = "REDUCE"
        else:
            signal = "HOLD"
    signals.append(signal)

df["Signal"] = signals

# ==============================
# DISPLAY
# ==============================

st.markdown("## 📊 Portfolio & Rotation Signals")

def color_signal(val):
    if val == "BUY":
        return "background-color:#b6f2c2"
    if val == "REDUCE":
        return "background-color:#f7b2b2"
    return ""

styled = df.style.format({
    "Momentum": "{:.2%}",
    "Volatility": "{:.4f}",
    "Price": "${:.2f}",
    "Value": "${:,.0f}",
    "Weight": "{:.1%}",
    "Score": "{:.1f}"
}).applymap(color_signal, subset=["Signal"])

st.dataframe(styled, use_container_width=True)
st.metric("💼 Portfolio Value", f"${total_value:,.0f}")

# ==============================
# ROTATION PLAN
# ==============================

st.markdown("## 🔄 What To Do Now")

buys = df[df["Signal"] == "BUY"]
sells = df[df["Signal"] == "REDUCE"]

if len(buys) == 0 and len(sells) == 0:
    st.info("No strong rotation needed today.")
else:
    if len(sells):
        for _, r in sells.iterrows():
            sell_amt = max(1, int(r["Shares"] * 0.15))
            st.error(f"🔴 Reduce {r['ETF']} → sell ~{sell_amt} shares")

    if len(buys):
        cash_each = cash_to_reinvest / len(buys)
        for _, r in buys.iterrows():
            buy_shares = int(cash_each // r["Price"])
            st.success(f"🟢 Add {r['ETF']} → buy ~{buy_shares} shares")

st.caption("Uses momentum + income weighting + portfolio exposure. Designed for weekly income rotation.")
