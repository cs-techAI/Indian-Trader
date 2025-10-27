# brokers/kite_broker.py
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import requests, math
from kiteconnect import KiteConnect
from config import settings

def _nse(sym: str) -> str:
    s = (sym or "").upper().strip()
    # Accept RELIANCE, TCS, INFY ... (You can extend mappings as needed)
    return f"NSE:{s}"

class KiteBroker:
    def __init__(self, api_key: str, access_token: str, openalgo_base: Optional[str] = None):
        self.openalgo = openalgo_base.rstrip("/") if openalgo_base else None
        self.kite = KiteConnect(api_key=api_key) if not self.openalgo else None
        if self.kite:
            if not access_token:
                raise RuntimeError("KITE_ACCESS_TOKEN missing. Run scripts/kite_login.py to generate.")
            self.kite.set_access_token(access_token)

    # ---- helpers for OpenAlgo (adjust to your instance if needed) ----
    def _oa_get(self, path: str, params=None):
        url = f"{self.openalgo}{path}"
        r = requests.get(url, params=params, timeout=15); r.raise_for_status(); return r.json()

    def _oa_post(self, path: str, payload: dict):
        url = f"{self.openalgo}{path}"
        r = requests.post(url, json=payload, timeout=15); r.raise_for_status(); return r.json()

    # ---- balances ----
    def account_balances(self) -> Dict[str, float]:
        if self.openalgo:
            # Example shape; adapt if your OpenAlgo differs
            j = self._oa_get("/funds")
            equity = float(j.get("equity", 0.0))
            cash = float(j.get("cash", 0.0))
        else:
            j = self.kite.margins("equity")
            cash = float(j.get("available", {}).get("cash", 0.0))
            equity = float(j.get("net", 0.0))
        return {
            "cash": cash,
            "equity": equity,
            "buying_power": equity,
            "portfolio_value": equity,
        }

    # ---- prices ----
    def last_price(self, symbol: str) -> Optional[float]:
        i = _nse(symbol)
        if self.openalgo:
            j = self._oa_get("/ltp", params={"i": i})
            # expect {"ltp": {"NSE:RELIANCE": 2860.5}}
            try:
                return float((j.get("ltp") or {}).get(i))
            except Exception:
                return None
        else:
            j = self.kite.ltp(i)
            try:
                return float(j[i]["last_price"])
            except Exception:
                return None

    # ---- positions ----
    def list_positions(self) -> List[Dict]:
        if self.openalgo:
            j = self._oa_get("/positions")
            data = j.get("data", [])
        else:
            pos = self.kite.positions()
            data = (pos.get("net") or [])  # [{'tradingsymbol','quantity','average_price','last_price',...}]
        out = []
        for p in data:
            sym = p.get("tradingsymbol") or p.get("symbol") or ""
            qty = float(p.get("quantity") or p.get("qty") or 0)
            avg = float(p.get("average_price") or p.get("avg_entry_price") or 0)
            last = float(p.get("last_price") or p.get("current_price") or 0)
            out.append({
                "symbol": sym,
                "qty": qty,
                "avg_entry_price": avg,
                "current_price": last,
                "market_value": qty * last,
                "asset_class": "equity",
            })
        return out

    def position_qty(self, symbol: str) -> float:
        sym = (symbol or "").upper()
        for p in self.list_positions():
            if (p.get("symbol") or "").upper() == sym:
                return float(p.get("qty") or 0)
        return 0.0

    # ---- orders ----
    def _place(self, symbol: str, side: str, qty: float) -> str:
        side = side.upper()
        qty_i = int(math.floor(qty))
        if qty_i <= 0:
            raise RuntimeError("Qty must be >= 1 for Kite equities.")
        if self.openalgo:
            payload = {
                "tradingsymbol": symbol.upper(),
                "exchange": "NSE",
                "transaction_type": side,    # BUY or SELL
                "order_type": "MARKET",
                "product": "CNC",            # or MIS/NRML per your need
                "quantity": qty_i,
                "validity": "DAY"
            }
            j = self._oa_post("/orders", payload)
            return str(j.get("order_id") or j.get("data", {}).get("order_id"))
        else:
            order_id = self.kite.place_order(
                exchange="NSE",
                tradingsymbol=symbol.upper(),
                transaction_type=self.kite.TRANSACTION_TYPE_BUY if side == "BUY" else self.kite.TRANSACTION_TYPE_SELL,
                quantity=qty_i,
                order_type=self.kite.ORDER_TYPE_MARKET,
                product=self.kite.PRODUCT_CNC,  # delivery; switch to MIS for intraday
                variety=self.kite.VARIETY_REGULAR,
                validity=self.kite.VALIDITY_DAY,
            )
            return str(order_id)

    def market_buy(self, symbol: str, qty: float) -> str:
        return self._place(symbol, "BUY", qty)

    def market_sell(self, symbol: str, qty: float) -> str:
        return self._place(symbol, "SELL", qty)

    def market_buy_qty(self, symbol: str, qty: float) -> Tuple[str, float, float]:
        # Kite returns order_id; we don't get fills synchronously—approx with LTP.
        ltp = self.last_price(symbol) or 0.0
        oid = self.market_buy(symbol, qty)
        return (oid, float(int(qty)), float(ltp))

    def close_position(self, symbol: str) -> str:
        qty = self.position_qty(symbol)
        if qty <= 0:
            return "noop"
        return self.market_sell(symbol, qty)
