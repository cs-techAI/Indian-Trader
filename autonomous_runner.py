# autonomous_runner.py
from __future__ import annotations
import os, json
from datetime import datetime, timezone
from typing import Dict, Any, List

from config import settings
from brokers import get_broker
from core.data_manager import DataManager
from core.debate import Debate, summarize_reason_2lines
from core.llm import LCTraderLLM
from core.policy import (
    compute_allowed_notional, clamp_qty_by_share_caps,
    too_soon_since_last_buy, hit_daily_buy_limit
)
from core.positions import read_ledger, write_ledger, set_timebox_on_entry, merge_entry
from core.semantic_memory import SemanticMemory
from core.store import save_run_dict
from agents.short_term_agent import ShortTermAgent
from agents.mid_term_agent import MidTermAgent
from agents.long_term_agent import LongTermAgent

STATE_DIR = "state"
RUN_LOG = os.path.join(STATE_DIR, "auto_runs.jsonl")
os.makedirs(STATE_DIR, exist_ok=True)

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def _append_run(line: Dict[str, Any]) -> None:
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    try: save_run_dict(line)
    except Exception: pass

def enforce_timeboxes(broker):
    # (same as your current version, using read_ledger/close_position)
    pass  # keep your existing implementation here

def run_once(symbol: str, is_crypto: bool = False, trigger: str = "bar_close_30m") -> Dict[str, Any]:
    sym = symbol.upper()
    broker = get_broker()
    dm = DataManager()
    try: sm = SemanticMemory()
    except Exception: sm = None
    llm = LCTraderLLM(api_key=settings.gemini_key)
    debate = Debate(enter_th=settings.mean_confidence_to_act, exit_th=settings.exit_confidence_to_act)

    snap = dm.layered_snapshot_crypto(sym) if is_crypto else dm.layered_snapshot(sym)
    short = ShortTermAgent("ShortTerm", llm, {})
    mid   = MidTermAgent("MidTerm", llm, {})
    long_ = LongTermAgent("LongTerm", llm, {}, sm)

    votes = []
    for ag in (short, mid, long_):
        d, c, raw = ag.vote(snap)
        votes.append({"agent": ag.name, "decision": d, "confidence": float(c), "raw": raw})
    decision = debate.horizon_decide(votes)
    reason = summarize_reason_2lines(votes, decision)

    acct = broker.account_balances()
    last = broker.last_price(sym) or 0.0

    ledger = read_ledger()
    held_qty_ledger = float((ledger.get(sym, {}) or {}).get("qty", 0.0))

    if decision["action"] == "SELL":
        if held_qty_ledger > 0.0:
            try:
                oid = broker.close_position(sym)
                ledger.pop(sym, None); write_ledger(ledger)
                line = {"when": _now_iso(), "symbol": sym, "trigger": trigger,
                        "decision": decision, "action": "SELL", "order_id": oid, "reason": reason}
                _append_run(line); return line
            except Exception as e:
                line = {"when": _now_iso(), "symbol": sym, "trigger": trigger,
                        "decision": decision, "action": "SELL_FAILED", "error": str(e)}
                _append_run(line); return line
        _append_run({"when": _now_iso(), "symbol": sym, "trigger": trigger, "decision": decision, "action":"SELL_NO_POSITION"}); 
        return {"action": "SELL_NO_POSITION"}

    if decision["action"] == "BUY":
        if last <= 0: 
            _append_run({"when": _now_iso(), "symbol": sym, "trigger": trigger, "decision": decision, "action":"SUGGEST_BUY", "reason":reason+" (no price)"})
            return {"action":"SUGGEST_BUY"}

        runs_for_symbol = []  # you can reuse your recent-run helper
        if hit_daily_buy_limit(sym, runs_for_symbol) or too_soon_since_last_buy(sym, runs_for_symbol):
            _append_run({"when":_now_iso(),"symbol":sym,"trigger":trigger,"decision":decision,"action":"SUGGEST_BUY","reason":reason+" (throttle)"})
            return {"action":"SUGGEST_BUY"}

        notional_allowed = compute_allowed_notional(decision.get("target_horizon"), acct["cash"], acct["equity"], held_qty_ledger * last)
        if notional_allowed <= 0:
            _append_run({"when":_now_iso(),"symbol":sym,"trigger":trigger,"decision":decision,"action":"SUGGEST_BUY","reason":reason+" (caps)"})
            return {"action":"SUGGEST_BUY"}

        desired_qty = notional_allowed / last
        desired_qty = clamp_qty_by_share_caps(desired_qty, held_qty_ledger)
        if desired_qty <= 0:
            _append_run({"when":_now_iso(),"symbol":sym,"trigger":trigger,"decision":decision,"action":"SUGGEST_BUY","reason":reason+" (share cap)"})
            return {"action":"SUGGEST_BUY"}

        oid, filled_qty, avg_px = broker.market_buy_qty(sym, desired_qty)
        merge_entry(ledger, sym, decision.get("target_horizon"), filled_qty, avg_px, filled_qty*avg_px, reset_timebox=False)
        write_ledger(ledger)
        line = {"when":_now_iso(),"symbol":sym,"trigger":trigger,"decision":decision,"action":"BUY",
                "qty":filled_qty,"entry_price":avg_px,"order_id":oid,"reason":reason}
        _append_run(line); return line

    _append_run({"when": _now_iso(), "symbol": sym, "trigger": trigger, "decision": decision, "action": "HOLD"})
    return {"action":"HOLD"}
