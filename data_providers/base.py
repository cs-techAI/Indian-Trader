# data_providers/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd

class BaseProvider(ABC):
    @abstractmethod
    def get_bars(self, symbol: str, interval: str, lookback_days: int) -> pd.DataFrame:
        """Return df with columns: time, open, high, low, close, volume, ticker"""
        raise NotImplementedError
