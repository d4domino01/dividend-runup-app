import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# ======================================================
# PAGE
# ======================================================

st.set_page_config(page_title="Income Rotation Engine", layout="centered")
st.title("🔥 Ultra-Aggressive Income Rotation Engine")
st.caption("Momentum + income-weighted ETF rotation for dividend compounding")

# ======================================================
# SETTINGS
# ======================================================

ETF_LIST = ["QDTE", "XDTE", "CHPY", "JEPQ", "AIPI"]
MARKET = "QQQ"
WINDOW = 120

# Monthly income per share (editable)
INCOME = {
    "QDTE": 0.12,
    "XDTE": 0.12,
    "CHPY": 0.52,
    "JEPQ": 0.57,
    "AIPI": 1.20,
}

# ======================================================
# HOLDINGS INPUT
# ======================================================

st.subheader("📥 Your Current Holdings")

holdings = {}
total_value = 0

for etf in ETF_LIST:
    shares = st.number_input(f"{etf} shares", min_value=0, value=0, step=1)
    holdings[etf] = shares

cash_balance = st.number_input("💵 Available Cash ($)", min_value=0.0, value=0.0, step=50.0)

# ======================================================
# DATA
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
# MARKET MODE
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
portfolio_value = 0
monthly_income_now = 0

for etf in ETF_LIST:
    df = get_intraday(etf)
    if df is None:
        continue

    mom, vol = calc_metrics(df)
    rel = mom - bench_mom
    price = float(df["Close"].iloc[-1])
    income = INCOME.get(etf, 0)

    value = holdings[etf] * price
    portfolio_value += value
    monthly_income_now += holdings[etf] * income

    score = (mom * 100 * 50) + (rel * 100 * 30) + (income * 10) - (vol * 1000 * 5)

    rows.append([etf, mom, rel, vol, income, price, score, value, df])

df_all = pd.DataFrame(rows, columns=[
    "ETF", "Momentum", "RelStrength", "Volatility",
    "Monthly Income", "Price", "Score", "Value", "Chart"
])

df_all = df_all.sort_values("Score", ascending=False).reset_index(drop=True)

# ======================================================
# ROTATION LOGIC
# ======================================================

top_etf = df_all.iloc[0]["ETF"]
signals = []
sell_plan = []
buy_plan = []

rotation_cash = cash_balance

for i, row in df_all.iterrows():

    etf = row["ETF"]
    shares = holdings[etf]

    if market_mode == "RISK-OFF":
        signal = "HOLD"
    else:
        if etf == top_etf:
            signal = "BUY / ADD"
        elif shares > 0 and row["Score"] < df_all.iloc[0]["Score"] * 0.6:
            signal = f"ROTATE → {top_etf}"

            sell_value = shares * row["Price"]
            rotation_cash += sell_value
            sell_plan.append([etf, shares, sell_value])
        else:
            signal = "HOLD"

    signals.append(signal)

df_all["Signal"] = signals

# ======================================================
# BUY PLAN
# ======================================================

top_price = df_all[df_all["ETF"] == top_etf]["Price"].iloc[0]
shares_to_buy = int(rotation_cash // top_price)
buy_cost = shares_to_buy * top_price

# ======================================================
# DISPLAY
# ======================================================

st.subheader("📊 Rotation Rankings")

def color_signal(val):
    if "BUY" in val:
        return "background-color:#b6f2c2"
    if "ROTATE" in val:
        return "background-color:#f7b2b2"
    return ""

styled = df_all.style.format({
    "Momentum": "{:.2%}",
    "RelStrength": "{:.2%}",
    "Volatility": "{:.4f}",
    "Monthly Income": "${:.2f}",
    "Price": "${:.2f}",
    "Score": "{:.1f}",
    "Value": "${:,.0f}",
}).applymap(color_signal, subset=["Signal"])

st.dataframe(styled, use_container_width=True)

# ======================================================
# ROTATION ACTIONS
# ======================================================

st.subheader("🔄 Suggested Trades")

if len(sell_plan) == 0 and shares_to_buy == 0:
    st.info("No rotation needed today.")
else:
    if sell_plan:
        st.markdown("### ❌ Sell")
        sell_df = pd.DataFrame(sell_plan, columns=["ETF", "Shares", "Value $"])
        st.dataframe(sell_df)

    if shares_to_buy > 0:
        st.markdown("### ✅ Buy")
        st.success(f"Buy **{shares_to_buy} shares of {top_etf}** ≈ ${buy_cost:,.0f}")

# ======================================================
# INCOME TRACKING
# ======================================================

new_income = monthly_income_now - sum(
    s[1] * INCOME[s[0]] for s in sell_plan
) + shares_to_buy * INCOME[top_etf]

st.subheader("📈 Portfolio Income")

col1, col2, col3 = st.columns(3)
col1.metric("Monthly Income Now", f"${monthly_income_now:,.2f}")
col2.metric("After Rotation", f"${new_income:,.2f}")
col3.metric("Change", f"${new_income - monthly_income_now:+.2f}")

# ======================================================
# CHARTS
# ======================================================

st.subheader("📈 Last 120-Minute % Price Move")

for _, row in df_all.iterrows():
    chart = row["Chart"]
    base = chart["Close"].iloc[0]
    pct = (chart["Close"] / base - 1) * 100
    st.line_chart(pct, height=130)

# ======================================================
# SUMMARY
# ======================================================

st.info(
    f"Top rotation target: **{top_etf}** | "
    f"Market mode: **{market_mode}** | "
    f"Rotation cash: **${rotation_cash:,.0f}**"
)

st.caption("Signals combine momentum, relative strength vs QQQ, and income weighting.")
