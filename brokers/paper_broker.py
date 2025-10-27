# brokers/paper_broker.py
from __future__ import annotations
import json, os, time
from typing import Dict, List, Tuple, Optional
from config import settings
from core.positions import read_ledger, write_ledger, merge_entry
from core.data_manager import DataManager

ACC_PATH = os.path.join("state", "paper_account.json")
os.makedirs("state", exist_ok=True)

def _read_acc():
    if not os.path.exists(ACC_PATH):
        acc = {"cash": float(settings.paper_starting_equity)}
        with open(ACC_PATH, "w") as f: json.dump(acc, f)
        return acc
    with open(ACC_PATH, "r") as f: return json.load(f)

def _write_acc(acc): 
    with open(ACC_PATH, "w") as f: json.dump(acc, f)

class PaperBroker:
    def __init__(self):
        self.dm = DataManager()

    def _px(self, symbol: str) -> Optional[float]:
        # try intraday first, else daily
        try:
            df = self.dm.get_intraday_short(symbol)
            if df is not None and not df.empty:
                return float(df["close"].iloc[-1])
        except Exception:
            pass
        try:
            df = self.dm.get_daily_mid(symbol)
            if df is not None and not df.empty:
                return float(df["close"].iloc[-1])
        except Exception:
            pass
        return None

    def account_balances(self) -> Dict[str, float]:
        acc = _read_acc()
        cash = float(acc.get("cash", 0.0))
        # equity = cash + market value of ledger
        mv = 0.0
        led = read_ledger()
        for sym, meta in led.items():
            last = self._px(sym) or 0.0
            mv += last * float(meta.get("qty", 0))
        equity = cash + mv
        return {
            "cash": cash, "equity": equity,
            "buying_power": equity, "portfolio_value": equity
        }

    def last_price(self, symbol: str) -> Optional[float]:
        return self._px(symbol)

    def list_positions(self) -> List[Dict]:
        out = []
        led = read_ledger()
        for sym, meta in led.items():
            last = self._px(sym) or 0.0
            qty = float(meta.get("qty", 0))
            avg = float(meta.get("entry_price", 0))
            out.append({
                "symbol": sym, "qty": qty,
                "avg_entry_price": avg,
                "current_price": last,
                "market_value": qty * last,
                "asset_class": "equity",
            })
        return out

    def position_qty(self, symbol: str) -> float:
        return float((read_ledger().get(symbol, {}) or {}).get("qty", 0))

    def market_buy(self, symbol: str, qty: float) -> str:
        return self.market_buy_qty(symbol, float(qty))[0]

    def market_sell(self, symbol: str, qty: float) -> str:
        led = read_ledger()
        qty = float(qty)
        px = self._px(symbol) or 0.0
        if px <= 0: raise RuntimeError("No price for paper sell.")
        held = float((led.get(symbol, {}) or {}).get("qty", 0))
        if qty > held: qty = held
        # cash increases
        acc = _read_acc()
        acc["cash"] = float(acc.get("cash", 0.0)) + qty * px
        _write_acc(acc)
        # reduce ledger
        if symbol in led:
            new_qty = held - qty
            if new_qty <= 1e-12:
                led.pop(symbol, None)
            else:
                # keep same entry_price for remainder
                led[symbol]["qty"] = new_qty
                led[symbol]["notional"] = new_qty * float(led[symbol].get("entry_price", px))
        write_ledger(led)
        return f"paper-sell-{int(time.time())}"

    def market_buy_qty(self, symbol: str, qty: float) -> Tuple[str, float, float]:
        qty = float(qty)
        px = self._px(symbol) or 0.0
        if px <= 0: raise RuntimeError("No price for paper buy.")
        acc = _read_acc()
        cost = qty * px
        if cost > float(acc.get("cash", 0.0)):
            # buy what we can
            qty = float(acc.get("cash", 0.0)) / px
            cost = qty * px
        acc["cash"] = float(acc.get("cash", 0.0)) - cost
        _write_acc(acc)
        # ledger merge
        led = read_ledger()
        merge_entry(led, symbol, horizon="mid", add_qty=qty, add_price=px, add_notional=cost, reset_timebox=False)
        write_ledger(led)
        return (f"paper-buy-{int(time.time())}", qty, px)

    def close_position(self, symbol: str) -> str:
        qty = self.position_qty(symbol)
        if qty <= 0: return f"paper-close-{int(time.time())}"
        return self.market_sell(symbol, qty)
