# brokers/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional

class BaseBroker(ABC):
    """Common surface used by UI + automation."""

    @abstractmethod
    def account_balances(self) -> Dict[str, float]:
        """Return {'cash': float, 'equity': float, 'buying_power': float, 'portfolio_value': float}"""
        raise NotImplementedError

    @abstractmethod
    def last_price(self, symbol: str) -> Optional[float]:
        raise NotImplementedError

    @abstractmethod
    def list_positions(self) -> List[Dict]:
        """Return list of {'symbol','qty','avg_entry_price','current_price','market_value','asset_class'}"""
        raise NotImplementedError

    @abstractmethod
    def position_qty(self, symbol: str) -> float:
        raise NotImplementedError

    @abstractmethod
    def market_buy(self, symbol: str, qty: float) -> str:
        """Returns order_id"""
        raise NotImplementedError

    @abstractmethod
    def market_sell(self, symbol: str, qty: float) -> str:
        raise NotImplementedError

    @abstractmethod
    def market_buy_qty(self, symbol: str, qty: float) -> Tuple[str, float, float]:
        """Returns (order_id, filled_qty, avg_price)"""
        raise NotImplementedError

    @abstractmethod
    def close_position(self, symbol: str) -> str:
        raise NotImplementedError
