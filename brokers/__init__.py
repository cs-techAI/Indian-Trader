# brokers/__init__.py
from .base import BaseBroker
from .paper_broker import PaperBroker
from .kite_broker import KiteBroker
from config import settings

def get_broker() -> BaseBroker:
    if settings.broker == "PAPER":
        return PaperBroker()
    # default to KITE
    return KiteBroker(
        api_key=settings.kite_api_key,
        access_token=settings.kite_access_token,
        openalgo_base=settings.openalgo_base_url or None,
    )
