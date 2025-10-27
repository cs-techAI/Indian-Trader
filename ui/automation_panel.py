# ui/automation_panel.py
from __future__ import annotations
import os, json
from datetime import datetime, timezone
from typing import List, Dict, Any
import pandas as pd
import streamlit as st

from core.positions import read_ledger
from brokers import get_broker
from config import settings

RUN_LOG_PATH = os.path.join("state", "auto_runs.jsonl")

def _to_local(ts_iso: str) -> str:
    try:
        dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts_iso

def _read_last_jsonl(path: str, max_lines: int = 500) -> List[Dict[str, Any]]:
    if not os.path.exists(path): return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: out.append(json.loads(line))
            except Exception: pass
    return out[-max_lines:]

def _positions_df():
    broker = get_broker()
    ledger = read_ledger()
    rows = []
    for sym, meta in ledger.items():
        last = broker.last_price(sym) or None
        qty = float(meta.get("qty", 0))
        entry = float(meta.get("entry_price", 0))
        mv = (last * qty) if (last and qty) else None
        notional = float(meta.get("notional", 0))
        pnl = (mv - notional) if (mv is not None and notional) else None
        rows.append({
            "Symbol": sym, "Horizon": meta.get("horizon"),
            "Qty": qty, "Entry Price": round(entry,4) if entry else None,
            "Last Price": round(last,4) if last else None,
            "Market Value": round(mv,2) if mv is not None else None,
            "P&L": round(pnl,2) if pnl is not None else None,
            "Entered At": meta.get("entered_at",""),
            "Timebox Until": meta.get("timebox_until","-"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by=["Horizon","Symbol"]).reset_index(drop=True)
    return df

def render_automation_tab():
    st.subheader("⚙️ Automation — Loops, Decisions & Positions")
    broker = get_broker()
    acct = broker.account_balances()
    c1, c2, c3 = st.columns(3)
    c1.metric("Cash", f"{acct['cash']:.2f}")
    c2.metric("Equity", f"{acct['equity']:.2f}")
    c3.metric("Buying Power", f"{acct['buying_power']:.2f}")

    st.divider()
    st.markdown("### 📦 Open Positions (Ledger)")
    pos_df = _positions_df()
    st.dataframe(pos_df, use_container_width=True, height=260)

    st.divider()
    st.markdown("### 📜 Recent Automation Runs")
    runs = _read_last_jsonl(RUN_LOG_PATH, 300)
    if runs:
        df = pd.DataFrame(runs).sort_values("when", ascending=False)
        view = ["when","symbol","trigger","action","decision","qty","entry_price","order_id","reason"]
        st.dataframe(df[[c for c in view if c in df.columns]], use_container_width=True, height=360)
    else:
        st.info("No runs yet.")
