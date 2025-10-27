# core/data_manager.py
from __future__ import annotations
import os
import pandas as pd
from datetime import datetime, timedelta
from config import settings
from data_providers import get_provider
from core.indicators import enrich_indicators

_REQUIRED = ["close","rsi","macd","macd_signal","upper_band","lower_band"]

def _drop_indicator_nans(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty: return df
    cols = ["close"] + [c for c in _REQUIRED if c in df.columns]
    cols = list(dict.fromkeys(cols))
    return df.dropna(subset=[c for c in cols if c in df.columns])

class DataManager:
    def __init__(self, data_dir: str | None = None):
        self.data_dir = data_dir or settings.data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.provider = get_provider()

    def _cache_path(self, symbol: str, kind: str) -> str:
        safe = symbol.upper().replace("/", "_")
        return os.path.join(self.data_dir, f"{safe}_{kind}.parquet")

    def _is_stale(self, path: str, max_age_minutes: int) -> bool:
        if not os.path.exists(path): return True
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        return (datetime.now() - mtime) > timedelta(minutes=max_age_minutes)

    def _read_parquet(self, path: str) -> pd.DataFrame:
        try:
            df = pd.read_parquet(path)
            df.columns = [c.lower().strip() for c in df.columns]
            if "time" not in df.columns:
                for cand in ("date","datetime","Datetime","Date"):
                    if cand in df.columns:
                        df = df.rename(columns={cand: "time"})
                        break
            return df
        except Exception:
            return pd.DataFrame()

    # ------------- Stocks (no crypto in Kite) -------------
    def _fetch(self, symbol: str, interval: str, lookback_days: int, max_age_min: int, kind: str) -> pd.DataFrame:
        path = self._cache_path(symbol, kind)
        if self._is_stale(path, max_age_min):
            df = self.provider.get_bars(symbol, interval=interval, lookback_days=lookback_days)
            if not df.empty:
                df.to_parquet(path, index=False)
        else:
            df = self._read_parquet(path)
            if df.empty:
                df = self.provider.get_bars(symbol, interval=interval, lookback_days=lookback_days)
                if not df.empty:
                    df.to_parquet(path, index=False)
        if df is None or df.empty: return df
        df = enrich_indicators(df)
        return _drop_indicator_nans(df)

    def get_intraday_short(self, symbol: str) -> pd.DataFrame:
        return self._fetch(symbol, settings.short_interval, lookback_days=60, max_age_min=15, kind=settings.short_interval)

    def get_daily_mid(self, symbol: str) -> pd.DataFrame:
        return self._fetch(symbol, "1d", lookback_days=5*365, max_age_min=1440, kind="1d")

    def get_weekly_long(self, symbol: str) -> pd.DataFrame:
        return self._fetch(symbol, "1wk", lookback_days=10*365, max_age_min=1440, kind="1wk")

    def layered_snapshot(self, symbol: str) -> dict:
        return {
            "short_term": self.get_intraday_short(symbol),
            "mid_term":   self.get_daily_mid(symbol),
            "long_term":  self.get_weekly_long(symbol),
        }

    # ----- Crypto (only if enabled + YF provider) -----
    def layered_snapshot_crypto(self, symbol: str) -> dict:
        if not settings.enable_crypto:
            return {"short_term": pd.DataFrame(), "mid_term": pd.DataFrame(), "long_term": pd.DataFrame()}
        # yfinance will handle "BTC-USD" etc. map simple pairs "BTC/USD"->"BTC-USD"
        yf_sym = symbol.replace("/", "-")
        return {
            "short_term": self._fetch(yf_sym, settings.short_interval, 60, 15, f"CRYPTO_{settings.short_interval}"),
            "mid_term":   self._fetch(yf_sym, "1d", 5*365, 1440, "CRYPTO_1d"),
            "long_term":  self._fetch(yf_sym, "1wk", 10*365, 1440, "CRYPTO_1wk"),
        }
