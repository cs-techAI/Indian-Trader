# data_providers/kite_providers.py
from __future__ import annotations
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict
from kiteconnect import KiteConnect
from config import settings

_INTERVAL_MAP = {"30m": "30minute", "1d": "day", "1wk": "week"}

class KiteProvider:
    def __init__(self):
        self.kite = KiteConnect(api_key=settings.kite_api_key)
        if not settings.kite_access_token:
            raise RuntimeError("KITE_ACCESS_TOKEN missing for data provider.")
        self.kite.set_access_token(settings.kite_access_token)
        self._ins_cache: Dict[str, int] = {}  # symbol -> instrument_token

    def _token(self, symbol: str) -> int:
        s = symbol.upper().strip()
        if s in self._ins_cache:
            return self._ins_cache[s]
        # Download all instruments once; filter NSE
        instruments = self.kite.instruments("NSE")
        for it in instruments:
            if (it.get("tradingsymbol") or "").upper() == s:
                self._ins_cache[s] = int(it["instrument_token"])
                return self._ins_cache[s]
        raise RuntimeError(f"Symbol not found in NSE instruments: {symbol}")

    def get_bars(self, symbol: str, interval: str, lookback_days: int) -> pd.DataFrame:
        intr = _INTERVAL_MAP.get(interval, "day")
        to_dt = datetime.now()
        from_dt = to_dt - timedelta(days=lookback_days)
        token = self._token(symbol)
        candles = self.kite.historical_data(token, from_dt, to_dt, intr, continuous=False, oi=False)
        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame(candles)
        # candle keys: date, open, high, low, close, volume
        df = df.rename(columns={"date":"time"})
        df["ticker"] = symbol.upper()
        return df[["time","open","high","low","close","volume","ticker"]]
