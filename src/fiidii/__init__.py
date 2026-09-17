"""FII-DII-Decode: conditional next-day OI plans and positional carry context.

Package layout
--------------
- nse.py        : session + low-level NSE fetch helpers (cookies, retries)
- fetch.py      : high-level daily data collectors (participant OI, cash, option chain)
- store.py      : local CSV/JSON persistence + history loading
- decode.py     : the decode engine (methodology from the channel transcript)
- levels.py     : option-chain based institutional level derivation
- predict.py    : next-day & next-week prediction assembly
- backtest.py   : point-in-time historical replay + accuracy metrics
- report.py     : render HTML/markdown report
- email_send.py : deliver report via email (SMTP)
- cli.py        : entry point wiring everything together
"""

__version__ = "0.1.0"
