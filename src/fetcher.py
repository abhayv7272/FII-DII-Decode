import os
import urllib.request
import datetime
import sqlite3
import pandas as pd
import yfinance as yf
import json
import time
import random

class FreeDataFetcher:
    def __init__(self, config_path="config.json", db_path="data/participant_oi_master.db"):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, config_path)
        self.db_path = os.path.join(self.base_dir, db_path)
        
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        else:
            self.config = {
                "recipient_email": "abhayv7272@gmail.com",
                "sectors": [],
                "macro_tickers": {}
            }
            
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
        ]

    def _get_headers(self):
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

    def fetch_latest_participant_oi(self, target_date=None):
        """
        Ultra-resilient NSE Participant-wise OI fetcher with multi-endpoint fallback,
        automatic date backtrack up to 15 days, and SQLite database fallback.
        """
        if target_date is None:
            cur_date = datetime.date.today()
        else:
            cur_date = target_date

        print(f"[INFO] Scanning for latest official NSE Participant OI starting from: {cur_date}")

        for offset in range(15):
            d = cur_date - datetime.timedelta(days=offset)
            if d.weekday() >= 5: # Skip Saturday/Sunday
                continue
            
            d_str = d.strftime("%d%m%Y")
            urls = [
                f"https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{d_str}.csv",
                f"https://archives.nseindia.com/content/nsccl/fao_participant_oi_{d_str}.csv",
                f"https://www.nseindia.com/content/nsccl/fao_participant_oi_{d_str}.csv",
                f"https://archives.nseindia.com/archives/fo/fao_participant_oi_{d_str}.csv"
            ]
            
            for url in urls:
                for retry in range(2):
                    try:
                        req = urllib.request.Request(url, headers=self._get_headers())
                        with urllib.request.urlopen(req, timeout=6) as resp:
                            if resp.status == 200:
                                content = resp.read().decode("utf-8", errors="ignore")
                                if "Client Type" in content and len(content) > 300:
                                    records = self._parse_participant_csv(content, d.strftime("%Y-%m-%d"))
                                    if records and len(records) >= 4:
                                        self._save_to_db(records)
                                        print(f"[SUCCESS] Fetched official NSE file for {d.strftime('%Y-%m-%d')} from {url}")
                                        return {
                                            "date": d.strftime("%Y-%m-%d"),
                                            "display_date": d.strftime("%d %B %Y"),
                                            "raw_data": records,
                                            "status": "success",
                                            "source": "live_nse_exchange",
                                            "url": url
                                        }
                    except Exception:
                        time.sleep(0.3)
                        continue
        
        print("[WARNING] Live network fetch timed out or market closed. Falling back to cached historical SQLite DB.")
        return self._get_latest_from_db()

    def _parse_participant_csv(self, content, date_str):
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        header_idx = -1
        for idx, line in enumerate(lines[:10]):
            if "Client Type" in line:
                header_idx = idx
                break
        if header_idx == -1:
            return None
        
        records = []
        for line in lines[header_idx+1:]:
            parts = [p.strip().replace("\t", "").replace('"', '').replace(',', '') for p in line.split(",")]
            # In some CSV lines commas were separators; let's split with csv reader logic
            raw_parts = [p.strip().replace("\t", "").replace('"', '') for p in line.split(",")]
            if len(raw_parts) >= 15:
                client_type = raw_parts[0].strip()
                if client_type in ["Client", "DII", "FII", "Pro", "TOTAL"]:
                    try:
                        def parse_int(val):
                            v = val.strip().replace(",", "").replace('"', '')
                            return int(v) if (v.lstrip("-").isdigit()) else 0

                        records.append({
                            "date": date_str,
                            "client_type": client_type,
                            "future_index_long": parse_int(raw_parts[1]),
                            "future_index_short": parse_int(raw_parts[2]),
                            "future_stock_long": parse_int(raw_parts[3]),
                            "future_stock_short": parse_int(raw_parts[4]),
                            "option_index_call_long": parse_int(raw_parts[5]),
                            "option_index_put_long": parse_int(raw_parts[6]),
                            "option_index_call_short": parse_int(raw_parts[7]),
                            "option_index_put_short": parse_int(raw_parts[8]),
                            "option_stock_call_long": parse_int(raw_parts[9]),
                            "option_stock_put_long": parse_int(raw_parts[10]),
                            "option_stock_call_short": parse_int(raw_parts[11]),
                            "option_stock_put_short": parse_int(raw_parts[12]),
                            "total_long_contracts": parse_int(raw_parts[13]),
                            "total_short_contracts": parse_int(raw_parts[14]),
                        })
                    except Exception as e:
                        continue
        return records

    def _save_to_db(self, records):
        if not records or not os.path.exists(self.db_path):
            return
        try:
            conn = sqlite3.connect(self.db_path)
            cur_date = records[0]["date"]
            conn.execute(f"DELETE FROM participant_oi_raw WHERE date = '{cur_date}'")
            df_new = pd.DataFrame(records)
            df_new.to_sql("participant_oi_raw", conn, if_exists="append", index=False)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB_ERROR] Failed to cache to SQLite: {e}")

    def _get_latest_from_db(self):
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database {self.db_path} not found.")
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql("SELECT * FROM participant_oi_raw ORDER BY date DESC LIMIT 20", conn)
        conn.close()
        if df.empty:
            raise ValueError("No participant data found in database.")
        latest_date = df["date"].iloc[0]
        records = df[df["date"] == latest_date].to_dict(orient="records")
        return {
            "date": latest_date,
            "display_date": pd.to_datetime(latest_date).strftime("%d %B %Y"),
            "raw_data": records,
            "status": "success",
            "source": "sqlite_cache_latest"
        }

    def fetch_recent_history(self, days_count=15):
        """Fetches the last N trading days from SQLite for multi-day delta calculations."""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql(f"""
            SELECT * FROM participant_oi_raw 
            WHERE date IN (
                SELECT DISTINCT date FROM participant_oi_raw ORDER BY date DESC LIMIT {days_count}
            )
            ORDER BY date ASC
        """, conn)
        conn.close()
        return df

    def fetch_global_macro(self):
        """Fetches live/EOD Brent crude, US 10Y yields, DXY, and US Market performance with fallbacks."""
        macro_dict = {}
        fallback_map = {
            "brent_crude": ["BZ=F", "CL=F"],
            "us_10y_yield": ["^TNX", "10Y"],
            "us_dollar_index": ["DX-Y.NYB", "UUP"],
            "dow_jones": ["^DJI", "DIA"],
            "sp500": ["^GSPC", "SPY"],
            "nifty_50": ["^NSEI", "NIFTYBEES.NS"],
            "bank_nifty": ["^NSEBANK", "BANKBEES.NS"]
        }

        for key, tickers in fallback_map.items():
            val = {"symbol": tickers[0], "current": 0.0, "previous": 0.0, "change_pct": 0.0}
            for sym in tickers:
                try:
                    t = yf.Ticker(sym)
                    h = t.history(period="5d")
                    if not h.empty and len(h) >= 2:
                        curr_px = float(h["Close"].iloc[-1])
                        prev_px = float(h["Close"].iloc[-2])
                        chg_pct = float((curr_px / prev_px - 1) * 100)
                        val = {
                            "symbol": sym,
                            "current": round(curr_px, 2),
                            "previous": round(prev_px, 2),
                            "change_pct": round(chg_pct, 2)
                        }
                        break
                except Exception:
                    continue
            macro_dict[key] = val
        return macro_dict

    def fetch_sector_strength(self):
        """
        Ultra-resilient Sector Fetcher covering ALL 16 Official Indian Sectors
        with Primary, Secondary and Constituent fallbacks.
        """
        sector_definitions = [
            {"name": "Nifty Bank", "tickers": ["^NSEBANK", "BANKBEES.NS", "HDFCBANK.NS"], "description": "Banking & Financial Leaders"},
            {"name": "Nifty PSU Bank", "tickers": ["PSUBNKBEES.NS", "^CNXPSUBANK", "SBIN.NS"], "description": "Public Sector Banks (SBI, PNB, BOB)"},
            {"name": "Nifty IT", "tickers": ["^CNXIT", "ITBEES.NS", "TCS.NS"], "description": "Information Technology & Software (TCS, INFY)"},
            {"name": "Nifty Pharma", "tickers": ["^CNXPHARMA", "PHARMABEES.NS", "SUNPHARMA.NS"], "description": "Pharma & Formulations (Sun, Dr Reddy)"},
            {"name": "Nifty Healthcare", "tickers": ["HEALTHADD.NS", "APOLLOHOSP.NS", "MAXHEALTH.NS"], "description": "Hospitals & Diagnostics (Apollo, Max)"},
            {"name": "Nifty Auto", "tickers": ["AUTOBEES.NS", "^CNXAUTO", "TATAMOTORS.NS"], "description": "Automobiles, EVs & Ancillaries (M&M, Tata Motors)"},
            {"name": "Nifty FMCG", "tickers": ["FMCGIETF.NS", "ITC.NS", "HINDUNILVR.NS"], "description": "Consumer Goods & Staples (ITC, HUL)"},
            {"name": "Nifty Metal", "tickers": ["TATASTEEL.NS", "METALIETF.NS", "JSWSTEEL.NS"], "description": "Steel, Aluminum & Mining (Tata Steel, JSW)"},
            {"name": "Nifty Energy", "tickers": ["RELIANCE.NS", "ENERGYETF.NS", "NTPC.NS"], "description": "Power, Refining & Green Energy (Reliance, NTPC)"},
            {"name": "Nifty Oil & Gas", "tickers": ["ONGC.NS", "OIL.NS", "GAIL.NS"], "description": "Petroleum, Exploration & Gas (ONGC, GAIL)"},
            {"name": "Nifty Infrastructure", "tickers": ["CPSEETF.NS", "LT.NS", "ADANIPORTS.NS"], "description": "Infra, Ports, Roads & Engineering (L&T, Adani)"},
            {"name": "Nifty Realty", "tickers": ["DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS"], "description": "Real Estate & Construction (DLF, Godrej Prop)"},
            {"name": "Nifty Consumer Durables", "tickers": ["CONSUMBEES.NS", "TITAN.NS", "HAVELLS.NS"], "description": "Electronics, Appliances & Lifestyle (Titan, Havells)"},
            {"name": "Nifty Financial Services", "tickers": ["FINIETF.NS", "BAJFINANCE.NS", "HDFCLIFE.NS"], "description": "FinNifty, NBFCs & Insurance (Bajaj Finance)"},
            {"name": "Nifty Midcap 50", "tickers": ["^NSEMDCP50", "MID150BEES.NS"], "description": "Midcap High-Beta Growth Champions"},
            {"name": "Nifty Smallcap", "tickers": ["HDFCSML250.NS", "SMLCAP.NS"], "description": "Smallcap Momentum High-Alpha Leaders"}
        ]

        # Calculate Nifty benchmark returns
        nifty_1m_chg = 0.0
        nifty_1w_chg = 0.0
        for n_sym in ["^NSEI", "NIFTYBEES.NS"]:
            try:
                nh = yf.Ticker(n_sym).history(period="1mo")
                if not nh.empty and len(nh) >= 5:
                    nifty_1m_chg = float((nh["Close"].iloc[-1] / nh["Close"].iloc[0] - 1) * 100)
                    nifty_1w_chg = float((nh["Close"].iloc[-1] / nh["Close"].iloc[-5] - 1) * 100)
                    break
            except Exception:
                continue

        sector_results = []
        for sec in sector_definitions:
            name = sec["name"]
            desc = sec["description"]
            success = False
            
            for ticker in sec["tickers"]:
                try:
                    t = yf.Ticker(ticker)
                    h = t.history(period="1mo")
                    if not h.empty and len(h) >= 5:
                        cur_close = float(h["Close"].iloc[-1])
                        chg_1d = float((h["Close"].iloc[-1] / h["Close"].iloc[-2] - 1) * 100)
                        chg_1w = float((h["Close"].iloc[-1] / h["Close"].iloc[-5] - 1) * 100)
                        chg_1m = float((h["Close"].iloc[-1] / h["Close"].iloc[0] - 1) * 100)
                        
                        ema20 = float(h["Close"].ewm(span=20, adjust=False).mean().iloc[-1])
                        above_ema20 = cur_close >= (ema20 * 0.995) # 0.5% buffer tolerance
                        
                        rs_score = round(chg_1w - nifty_1w_chg + (chg_1m - nifty_1m_chg) * 0.5, 2)
                        
                        if rs_score > 2.0 and above_ema20:
                            status = "LEADER (Strong Outperformance)"
                            status_code = "LEADER"
                        elif rs_score > 0.0:
                            status = "IMPROVING (Outperforming)"
                            status_code = "IMPROVING"
                        elif rs_score > -2.5:
                            status = "NEUTRAL (In Line)"
                            status_code = "NEUTRAL"
                        else:
                            status = "LAGGARD (Underperforming)"
                            status_code = "LAGGARD"
                            
                        sector_results.append({
                            "name": name,
                            "ticker": ticker,
                            "description": desc,
                            "current": round(cur_close, 2),
                            "chg_1d": round(chg_1d, 2),
                            "chg_1w": round(chg_1w, 2),
                            "chg_1m": round(chg_1m, 2),
                            "above_20_ema": above_ema20,
                            "rs_score": rs_score,
                            "status": status,
                            "status_code": status_code
                        })
                        success = True
                        break
                except Exception:
                    continue
            
            # If all tickers fail for a sector, provide a neutral fallback placeholder
            if not success:
                sector_results.append({
                    "name": name,
                    "ticker": sec["tickers"][0],
                    "description": desc,
                    "current": 100.0,
                    "chg_1d": 0.0,
                    "chg_1w": 0.0,
                    "chg_1m": 0.0,
                    "above_20_ema": True,
                    "rs_score": 0.0,
                    "status": "NEUTRAL (In Line)",
                    "status_code": "NEUTRAL"
                })

        sector_results.sort(key=lambda x: x["rs_score"], reverse=True)
        return sector_results
