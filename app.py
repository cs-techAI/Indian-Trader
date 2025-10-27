import os, json
from datetime import datetime
from typing import List, Dict
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from config import settings
from brokers import get_broker
from core.data_manager import DataManager
from core.finnhub_client import FinnhubClient
from core.semantic_memory import SemanticMemory
from core.llm import LCTraderLLM
from core.debate import Debate
from core.screeners import run_screener
from ui.automation_panel import render_automation_tab

from agents.short_term_agent import ShortTermAgent
from agents.mid_term_agent import MidTermAgent
from agents.long_term_agent import LongTermAgent

load_dotenv()
st.set_page_config(page_title="Three-Agent Trader (Kite/OpenAlgo)", page_icon="🤖", layout="wide")

st.sidebar.header("🔐 Keys & Toggles")
st.sidebar.write(f"Broker: **{settings.broker}** | Data: **{settings.data_source}**")
gemini_key = st.sidebar.text_input("Gemini API Key", value=settings.gemini_key or "", type="password")
finnhub_key = st.sidebar.text_input("Finnhub API Key", value=settings.finnhub_key or "", type="password")

st.sidebar.header("📈 Watchlist")
wl_stocks = st.sidebar.text_input("Stocks (comma sep)", value=settings.watchlist_stocks)

st.title("🤖 Three-Agent Trader — Kite/OpenAlgo + Paper + Screener")

tabs = ["Dashboard","Stocks","Screeners","News","Automation"]
if settings.enable_crypto:  # show only if allowed (YF)
    tabs.insert(2, "Crypto")
tab_objs = st.tabs(tabs)

def _agent_pack():
    dm = DataManager()
    sm = SemanticMemory()
    fh = FinnhubClient(api_key=finnhub_key) if finnhub_key else None
    llm = LCTraderLLM(api_key=gemini_key)
    debate = Debate()
    return dm, sm, fh, llm, debate

# ---------------- Dashboard ----------------
with tab_objs[0]:
    st.subheader("Portfolio Overview")
    broker = get_broker()
    try:
        acct = broker.account_balances()
        c1, c2, c3 = st.columns(3)
        c1.metric("Equity", f"{acct['equity']:.2f}")
        c2.metric("Cash", f"{acct['cash']:.2f}")
        c3.metric("Buying Power", f"{acct['buying_power']:.2f}")
        st.caption("Values shown in broker/base currency.")
    except Exception as e:
        st.warning(f"Account fetch failed: {e}")

    st.markdown("### Open Positions")
    try:
        pos = broker.list_positions()
        if pos:
            df = pd.DataFrame(pos)
            df = df.rename(columns={"symbol":"Symbol","qty":"Qty","avg_entry_price":"Avg Entry","current_price":"Last"})
            st.dataframe(df, use_container_width=True, height=380)
        else:
            st.info("No open positions.")
    except Exception as e:
        st.warning(f"Positions error: {e}")

# ---------------- Stocks ----------------
with tab_objs[1]:
    st.subheader("Stocks")
    dm, sm, fh, llm, debate = _agent_pack()
    col1, col2 = st.columns([2,1])
    with col1:
        sym = st.text_input("Symbol (NSE, e.g., RELIANCE, TCS)", value="RELIANCE").upper().strip()
    with col2:
        if st.button("Analyze (Stocks)", use_container_width=True):
            snapshot = dm.layered_snapshot(sym)
            if snapshot["mid_term"].empty:
                st.error("No data for this symbol.")
            else:
                short = ShortTermAgent("ShortTerm", llm, {})
                mid   = MidTermAgent("MidTerm", llm, {})
                long  = LongTermAgent("LongTerm", llm, {}, sm)
                votes = []
                for ag, df in ((short, snapshot),(mid, snapshot),(long, snapshot)):
                    d,c,raw = ag.vote(df)
                    votes.append({"agent":ag.name,"decision":d,"confidence":c,"raw":raw})
                decision = Debate(enter_th=settings.mean_confidence_to_act, exit_th=settings.exit_confidence_to_act).horizon_decide(votes)
                st.markdown("### Agent Votes")
                for v in votes:
                    st.write(f"• **{v['agent']}** → {v['decision']} (conf {v['confidence']:.2f})")
                st.markdown(f"**Final:** {decision['action']} (horizon={decision.get('target_horizon')}, conf={decision['confidence']:.2f})")

                st.divider()
                st.subheader("Place Market Order")
                side = st.radio("Side", ["BUY","SELL"], horizontal=True)
                qty = st.number_input("Qty (shares)", min_value=1, value=1, step=1)
                if st.button("Place Order"):
                    try:
                        broker = get_broker()
                        oid = broker.market_buy(sym, qty) if side=="BUY" else broker.market_sell(sym, qty)
                        st.success(f"Order placed: {oid}")
                    except Exception as e:
                        st.error(str(e))

# ---------------- Crypto (optional / YF) ----------------
offset = 2
if settings.enable_crypto:
    with tab_objs[2]:
        st.subheader("Crypto (YFinance provider)")
        dm, sm, fh, llm, debate = _agent_pack()
        col1, col2 = st.columns([2,1])
        with col1:
            symc = st.text_input("Crypto (BTC/USD, ETH/USD)", value="BTC/USD").upper().strip()
        with col2:
            if st.button("Analyze (Crypto)", use_container_width=True):
                snap = dm.layered_snapshot_crypto(symc)
                if snap["mid_term"].empty:
                    st.error("No data for this pair.")
                else:
                    short = ShortTermAgent("ShortTerm", llm, {})
                    mid   = MidTermAgent("MidTerm", llm, {})
                    long  = LongTermAgent("LongTerm", llm, {}, sm)
                    votes = []
                    for ag in (short, mid, long):
                        d,c,raw = ag.vote(snap)
                        votes.append({"agent":ag.name,"decision":d,"confidence":c,"raw":raw})
                    decision = Debate(enter_th=settings.mean_confidence_to_act, exit_th=settings.exit_confidence_to_act).horizon_decide(votes)
                    st.write(votes); st.write(decision)
else:
    offset = 0  # News is tab index 2 when crypto disabled

# ---------------- Screeners ----------------
with tab_objs[2 + offset]:
    st.subheader("Screeners — MACD / RSI / Fibonacci")
    dm = DataManager()
    syms = [s.strip().upper() for s in (st.text_area("Symbols (comma separated)", value=wl_stocks).split(",")) if s.strip()]
    tf = st.selectbox("Timeframe", ["1d","1wk","30m"], index=0)
    if st.button("Run Screener"):
        df = run_screener(syms, dm, timeframe=tf)
        st.dataframe(df, use_container_width=True, height=420)

# ---------------- News ----------------
with tab_objs[3 + offset]:
    st.subheader("Latest News (Finnhub)")
    if not finnhub_key:
        st.info("Enter Finnhub API key in the sidebar.")
    else:
        fh = FinnhubClient(api_key=finnhub_key)
        try:
            items = fh.general_news_struct(max_items=30)
            df = pd.DataFrame(items)
            if not df.empty:
                st.dataframe(df[["headline","source","url"]], use_container_width=True, height=360)
        except Exception as e:
            st.warning(str(e))

# ---------------- Automation ----------------
with tab_objs[4 + offset]:
    render_automation_tab()
