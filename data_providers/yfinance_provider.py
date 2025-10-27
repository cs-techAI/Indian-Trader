# data_providers/yfinace_provider.py
from __future__ import annotations
import pandas as pd, yfinance as yf
from datetime import datetime, timedelta
from .base import BaseProvider

class YFinanceProvider(BaseProvider):
    def _reset_time(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.reset_index()
        for cand in ("Datetime","Date","datetime","date"):
            if cand in df.columns:
                df = df.rename(columns={cand: "time"})
                break
        return df

    def _normalize(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if df.empty: return df
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        df.columns = [str(c).lower() for c in df.columns]
        if "adj close" in df.columns and "close" not in df.columns:
            df["close"] = df["adj close"]
        needed = {"open","high","low","close","volume"}
        if not needed.issubset(set(df.columns)):
            return pd.DataFrame()
        df["ticker"] = symbol.upper()
        return df[["time","open","high","low","close","volume","ticker"]]

    def get_bars(self, symbol: str, interval: str, lookback_days: int) -> pd.DataFrame:
        # map to yf interval / period
        if interval == "30m":
            yf_interval, period = "30m", "60d"
        elif interval == "1d":
            yf_interval, period = "1d", "5y"
        else:
            yf_interval, period = "1wk", "10y"

        raw = yf.download(symbol, period=period, interval=yf_interval, auto_adjust=True, progress=False)
        if raw is None or raw.empty: return raw
        df = self._reset_time(raw)
        return self._normalize(df, symbol)
