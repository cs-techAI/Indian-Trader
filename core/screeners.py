# core/screeners.py
from __future__ import annotations
import pandas as pd
from typing import List, Dict

def compute_fibonacci(df: pd.DataFrame, lookback: int = 120) -> Dict[str, float]:
    if df is None or df.empty: return {}
    sub = df.tail(lookback)
    high = float(sub["high"].max()); low = float(sub["low"].min())
    diff = high - low
    return {
        "0.0%": high,
        "23.6%": high - 0.236*diff,
        "38.2%": high - 0.382*diff,
        "50.0%": high - 0.5*diff,
        "61.8%": high - 0.618*diff,
        "78.6%": high - 0.786*diff,
        "100%": low,
    }

def rule_macd_cross(df: pd.DataFrame) -> str:
    if df is None or df.empty or "macd" not in df or "macd_signal" not in df:
        return "NO_DATA"
    a = df["macd"].iloc[-2] - df["macd_signal"].iloc[-2]
    b = df["macd"].iloc[-1] - df["macd_signal"].iloc[-1]
    if a <= 0 and b > 0: return "MACD_BULL_CROSS"
    if a >= 0 and b < 0: return "MACD_BEAR_CROSS"
    return "MACD_FLAT"

def rule_rsi(df: pd.DataFrame, low=35, high=65) -> str:
    if df is None or df.empty or "rsi" not in df: return "NO_DATA"
    r = float(df["rsi"].iloc[-1])
    if r < low: return "RSI_OVERSOLD"
    if r > high: return "RSI_OVERBOUGHT"
    return "RSI_NEUTRAL"

def rule_fib_bounce(df: pd.DataFrame, fib: Dict[str, float], pct=0.005) -> str:
    if not fib or df.empty: return "NO_DATA"
    close = float(df["close"].iloc[-1])
    for label, lvl in fib.items():
        if abs(close - float(lvl)) / max(1e-9, float(lvl)) <= pct:
            return f"FIB_NEAR_{label}"
    return "FIB_NONE"

def run_screener(symbols: List[str], dm, timeframe: str = "1d") -> pd.DataFrame:
    rows = []
    for s in symbols:
        if timeframe == "1d":
            df = dm.get_daily_mid(s)
        elif timeframe == "1wk":
            df = dm.get_weekly_long(s)
        else:
            df = dm.get_intraday_short(s)
        if df is None or df.empty:
            rows.append({"symbol": s, "status": "NO_DATA"}); continue
        fib = compute_fibonacci(df)
        rows.append({
            "symbol": s,
            "close": float(df["close"].iloc[-1]),
            "signal_macd": rule_macd_cross(df),
            "signal_rsi": rule_rsi(df),
            "signal_fib": rule_fib_bounce(df, fib),
        })
    return pd.DataFrame(rows)
