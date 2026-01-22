import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# ======================================================
# PAGE SETUP
# ======================================================

st.set_page_config(page_title="Income Rotation Engine", layout="centered")

st.title("🔥 Ultra-Aggressive Income Rotation Engine")
st.caption("Momentum + income-weighted ETF rotation for dividend compounding")

# ======================================================
# SETTINGS
# ======================================================

ETF_LIST = ["QDTE", "XDTE", "CHPY", "JEPQ", "AIPI"]
MARKET = "QQQ"
WINDOW = 120  # minutes

# Monthly income per share (your numbers)
INCOME = {
    "QDTE": 0.12,
    "XDTE": 0.12,
    "CHPY": 0.52,
    "JEPQ": 0.57,
    "AIPI": 1.20,
}

# ======================================================
# DATA FUNCTIONS
# ======================================================

@st.cache_data(ttl=300)
def get_intraday(ticker):
    data = yf.download(ticker, period="1d", interval="1m", progress=False)
    if data is None or len(data) < WINDOW:
        return None
    return data.tail(WINDOW)

def calc_metrics(df):
    start = df["Close"].iloc[0]
    end = df["Close"].iloc[-1]
    momentum = (end - start) / start
    vol = df["Close"].pct_change().std()
    return momentum, vol

# ======================================================
# MARKET REGIME
# ======================================================

bench_df = get_intraday(MARKET)

if bench_df is None:
    st.warning("Market data not available yet. Try closer to market close.")
    st.stop()

bench_mom, bench_vol = calc_metrics(bench_df)

if bench_mom > 0.003:
    market_mode = "RISK-ON"
elif bench_mom < -0.003:
    market_mode = "RISK-OFF"
else:
    market_mode = "NEUTRAL"

if market_mode == "RISK-ON":
    st.success("🟢 MARKET MODE: RISK-ON")
elif market_mode == "RISK-OFF":
    st.error("🔴 MARKET MODE: RISK-OFF")
else:
    st.warning("🟡 MARKET MODE: NEUTRAL")

st.metric("QQQ (last 120 min)", f"{bench_mom*100:.2f}%")

# ======================================================
# ETF ANALYSIS
# ======================================================

rows = []

for etf in ETF_LIST:
    df = get_intraday(etf)
    if df is None:
        continue

    mom, vol = calc_metrics(df)
    rel = mom - bench_mom

    price = float(df["Close"].iloc[-1])
    income = INCOME.get(etf, 0)

    # Rotation Score (tuned for income focus)
    score = (mom * 100 * 50) + (rel * 100 * 30) + (income * 10) - (vol * 1000 * 5)

    rows.append([etf, mom, rel, vol, income, price, score, df])

df_all = pd.DataFrame(rows, columns=[
    "ETF", "Momentum", "RelStrength", "Volatility",
    "Monthly Income", "Price", "Score", "Chart"
])

df_all = df_all.sort_values("Score", ascending=False).reset_index(drop=True)

# ======================================================
# SIGNAL LOGIC (ROTATION)
# ======================================================

signals = []
top_etf = df_all.iloc[0]["ETF"]

for i, row in df_all.iterrows():
    if market_mode == "RISK-OFF":
        signal = "REDUCE" if row["Momentum"] < 0 else "HOLD"
    else:
        if i == 0:
            signal = "BUY / ADD"
        elif row["Score"] < df_all.iloc[0]["Score"] * 0.6:
            signal = f"ROTATE → {top_etf}"
        else:
            signal = "HOLD"
    signals.append(signal)

df_all["Signal"] = signals

# ======================================================
# DISPLAY TABLE
# ======================================================

st.subheader("📊 Income-Weighted Rotation Rankings")

def color_signal(val):
    if "BUY" in val:
        return "background-color:#b6f2c2"
    if "ROTATE" in val or "REDUCE" in val:
        return "background-color:#f7b2b2"
    return ""

styled = df_all.style.format({
    "Momentum": "{:.2%}",
    "RelStrength": "{:.2%}",
    "Volatility": "{:.4f}",
    "Monthly Income": "${:.2f}",
    "Price": "${:.2f}",
    "Score": "{:.1f}",
}).applymap(color_signal, subset=["Signal"])

st.dataframe(styled, use_container_width=True)

# ======================================================
# CHARTS
# ======================================================

st.subheader("📈 Last 120-Minute % Price Movement")

for _, row in df_all.iterrows():
    chart = row["Chart"]
    base = chart["Close"].iloc[0]
    pct_line = (chart["Close"] / base - 1) * 100
    st.line_chart(pct_line, height=140)

# ======================================================
# SUMMARY
# ======================================================

top2 = ", ".join(df_all.head(2)["ETF"].tolist())

if market_mode == "RISK-OFF":
    summary = "Market weak — reduce risk, favor higher income + stability."
elif market_mode == "NEUTRAL":
    summary = f"Mixed market. Best income-momentum combo: {top2}. Add small or wait."
else:
    summary = f"Strong close momentum. Rotate capital toward: {top2}."

st.info(summary)

st.caption("Signals combine: 120-min momentum, relative strength vs QQQ, and monthly income weighting.")
