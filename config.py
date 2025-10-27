#config.py
import os
from dataclasses import dataclass

def _b(v, default=False):
    s = str(os.getenv(v, "1" if default else "0")).strip().lower()
    return s in ("1", "true", "yes", "y", "on")

@dataclass
class Settings:
    # broker & data source
    broker: str = os.getenv("BROKER", "KITE").upper()           # KITE | PAPER
    data_source: str = os.getenv("DATA_SOURCE", "KITE").upper() # KITE | YF
    enable_crypto: bool = _b("ENABLE_CRYPTO", default=False)

    # kite
    kite_api_key: str = os.getenv("KITE_API_KEY", "")
    kite_api_secret: str = os.getenv("KITE_API_SECRET", "")
    kite_access_token: str = os.getenv("KITE_ACCESS_TOKEN", "")
    openalgo_base_url: str = os.getenv("OPENALGO_BASE_URL", "")

    # paper
    paper_starting_equity: float = float(os.getenv("PAPER_STARTING_EQUITY", "100000"))

    # llm / finnhub / db (reuse)
    gemini_key: str = os.getenv("GEMINI_KEY", "")
    finnhub_key: str = os.getenv("FINNHUB_KEY", "")
    mysql_url: str = os.getenv("MYSQL_URL", "")

    # strategy thresholds
    mean_confidence_to_act: float = float(os.getenv("MEAN_CONF_TH", "0.60"))
    exit_confidence_to_act: float = float(os.getenv("EXIT_CONF_TH", "0.45"))

    # data manager lookbacks (reuse your old defaults)
    short_interval: str = "30m"
    short_period: str = "60d"
    short_lookback: int = 160
    mid_daily_lookback: int = 260
    long_weekly_lookback: int = 520

    # cache location
    data_dir: str = os.getenv("DATA_DIR", "data")

    # watchlists
    watchlist_stocks: str = os.getenv("WATCHLIST_STOCKS", "RELIANCE,TCS,INFY")
    watchlist_crypto: str = os.getenv("WATCHLIST_CRYPTO", "BTC/USD,ETH/USD")

settings = Settings()
