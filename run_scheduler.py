# run_scheduler.py
from __future__ import annotations
import os, threading, time
from typing import Dict
from apscheduler.schedulers.blocking import BlockingScheduler
from pytz import timezone
from config import settings
from brokers import get_broker
from autonomous_runner import run_once

ist = timezone("Asia/Kolkata")  # for indian time zone
sched = BlockingScheduler(timezone=ist)

WATCHLIST_STOCKS = [s.strip().upper() for s in settings.watchlist_stocks.split(",") if s.strip()]
WATCHLIST_CRYPTO = [s.strip().upper() for s in settings.watchlist_crypto.split(",") if s.strip()]

# Stock bar-close (09:30–15:30 IST) every 30 min at :02 and :32
@sched.scheduled_job("cron", day_of_week="mon-fri", hour="9-15", minute="2,32")
def stocks_halfhour():
    for s in WATCHLIST_STOCKS:
        print(run_once(s, is_crypto=False, trigger="bar_close_30m"))

# Optional crypto loop if enabled (YF only)
if settings.enable_crypto:
    @sched.scheduled_job("cron", minute="2,32")
    def crypto_halfhour():
        for c in WATCHLIST_CRYPTO:
            print(run_once(c, is_crypto=True, trigger="bar_close_30m"))

if __name__ == "__main__":
    sched.start()
