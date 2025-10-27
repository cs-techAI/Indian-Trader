# data_providers/__init__.py
from .base import BaseProvider
from .yfinance_provider import YFinanceProvider
from .kite_provider import KiteProvider
from config import settings

def get_provider() -> BaseProvider:
    if settings.data_source == "YF":
        return YFinanceProvider()
    return KiteProvider()
