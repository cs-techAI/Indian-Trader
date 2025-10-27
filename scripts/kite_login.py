# kite_login.py
"""
Usage:
  1) python scripts/kite_login.py
  2) Open the printed login URL, authorize, you'll be redirected with ?request_token=...
  3) Paste the request_token back; it prints the ACCESS_TOKEN for your .env
"""
import os
from kiteconnect import KiteConnect

api_key = os.getenv("KITE_API_KEY") or input("KITE_API_KEY: ").strip()
api_secret = os.getenv("KITE_API_SECRET") or input("KITE_API_SECRET: ").strip()

kite = KiteConnect(api_key=api_key)
print("Login URL:\n", kite.login_url())
rt = input("Paste request_token from redirect URL: ").strip()
session = kite.generate_session(rt, api_secret=api_secret)
print("\nACCESS_TOKEN:\n", session["access_token"])
