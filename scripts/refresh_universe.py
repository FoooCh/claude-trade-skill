"""Refresh the unified US + TW stock universe.

Outputs to $TRADE_HOME/universe/universe.md (default: ~/TradingAgents/universe/universe.md).

Sources:
- US: full S&P 500 component list from Wikipedia (no truncation, ~500 names)
- TW: all TWSE listed common stocks from isin.twse.com.tw, ranked by yfinance
  market cap, top 200 retained

Run weekly (or before starting a new screening cycle).

Override the output location by setting TRADE_HOME=/path/to/TradingAgents.
"""
from __future__ import annotations

import io
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import urllib3
import yfinance as yf

# TWSE's cert is missing the Subject Key Identifier extension. Their site is
# public data; we suppress the cert warning for that one host below.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TRADE_HOME = Path(os.environ.get("TRADE_HOME", Path.home() / "TradingAgents"))
OUT_PATH = TRADE_HOME / "universe" / "universe.md"
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
TWSE_LIST_URL = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

US_KEEP = 500
TW_KEEP = 200


def fetch_us_tickers() -> list[tuple[str, str]]:
    resp = requests.get(SP500_URL, headers={"User-Agent": UA}, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    df = tables[0]
    return [
        (row["Symbol"].replace(".", "-"), row["Security"])
        for _, row in df.iterrows()
    ]


def fetch_tw_tickers() -> list[tuple[str, str]]:
    """Return list of (code, name) for all TWSE listed common stocks."""
    resp = requests.get(TWSE_LIST_URL, headers={"User-Agent": UA}, timeout=30, verify=False)
    resp.encoding = "big5"
    tables = pd.read_html(io.StringIO(resp.text))
    df = tables[0]
    df.columns = df.iloc[0]
    df = df[1:]

    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _, row in df.iterrows():
        cell = str(row.iloc[0]).strip()
        m = re.match(r"^(\d{4})\s+(.+)$", cell)
        if not m:
            continue
        code, name = m.group(1), m.group(2).strip()
        if code in seen:
            continue
        if code.startswith("00"):  # skip ETFs / warrants
            continue
        seen.add(code)
        out.append((code, name))
    return out


def fetch_market_cap(yahoo_ticker: str, retries: int = 3) -> int | None:
    """Fetch market cap with throttle + 429 backoff. Let yfinance manage its own session."""
    for attempt in range(retries):
        try:
            info = yf.Ticker(yahoo_ticker).info
            mc = info.get("marketCap")
            time.sleep(0.15)
            return int(mc) if mc else None
        except Exception as e:
            msg = str(e)
            if "Too Many Requests" in msg or "429" in msg:
                wait = 5 * (attempt + 1)
                print(f"  ~ {yahoo_ticker} 429, sleeping {wait}s (attempt {attempt+1}/{retries})", flush=True)
                time.sleep(wait)
                continue
            print(f"  ! {yahoo_ticker} failed: {e}", file=sys.stderr)
            return None
    print(f"  ! {yahoo_ticker} gave up after {retries} retries", file=sys.stderr)
    return None


def fetch_usdtwd() -> float:
    """USD per 1 TWD. ~0.031 historically."""
    try:
        hist = yf.Ticker("TWD=X").history(period="5d")
        last = float(hist["Close"].iloc[-1])
        if last > 0:
            return 1.0 / last
    except Exception as e:
        print(f"  ! FX fetch failed: {e}", file=sys.stderr)
    return 1.0 / 32.0


def format_cap_usd(cap: int) -> str:
    if cap >= 1_000_000_000_000:
        return f"${cap / 1e12:.2f}T"
    if cap >= 1_000_000_000:
        return f"${cap / 1e9:.1f}B"
    return f"${cap / 1e6:.0f}M"


def main() -> int:
    print("=== Fetching ticker lists ===")
    print("  US: S&P 500 from Wikipedia...")
    us_tickers = fetch_us_tickers()
    print(f"    got {len(us_tickers)} US tickers")
    print("  TW: TWSE listed common stocks...")
    tw_tickers = fetch_tw_tickers()
    print(f"    got {len(tw_tickers)} TW common stock tickers")

    print("\n=== Fetching US market caps (yfinance) ===")
    us_rows: list[tuple[str, str, str, int]] = []
    for i, (tkr, name) in enumerate(us_tickers, 1):
        cap = fetch_market_cap(tkr)
        if cap is not None:
            us_rows.append(("US", tkr, name, cap))
        if i % 50 == 0:
            print(f"  US progress: {i}/{len(us_tickers)}", flush=True)
    us_rows.sort(key=lambda r: r[3], reverse=True)
    us_top = us_rows[:US_KEEP]
    print(f"  retained top {len(us_top)} US names")

    print("\n=== Fetching FX (USD/TWD) ===")
    usd_per_twd = fetch_usdtwd()
    print(f"  1 TWD = ${usd_per_twd:.5f}  (i.e. 1 USD = NT${1/usd_per_twd:.2f})")

    print("\n=== Fetching TW market caps (yfinance, slow) ===")
    tw_rows: list[tuple[str, str, str, int]] = []
    for i, (code, name) in enumerate(tw_tickers, 1):
        yahoo_ticker = f"{code}.TW"
        cap_twd = fetch_market_cap(yahoo_ticker)
        if cap_twd is not None:
            cap_usd = int(cap_twd * usd_per_twd)
            tw_rows.append(("TW", yahoo_ticker, name, cap_usd))
        if i % 50 == 0:
            print(f"  TW progress: {i}/{len(tw_tickers)}", flush=True)
    tw_rows.sort(key=lambda r: r[3], reverse=True)
    tw_top = tw_rows[:TW_KEEP]
    print(f"  retained top {len(tw_top)} TW names")

    all_rows = us_top + tw_top
    all_rows.sort(key=lambda r: r[3], reverse=True)
    print(f"\nTotal universe size: {len(all_rows)}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"# Screening Universe — US {len(us_top)} + TW {len(tw_top)} (refreshed {today})",
        "",
        "Sources: US = S&P 500 components (Wikipedia). TW = TWSE listed common stocks ranked by yfinance market cap.",
        "Refresh weekly via `scripts/refresh_universe.py`.",
        "",
        "Status legend: `pending` not yet analyzed | `done` analyzed and scored | `skip` excluded",
        "",
        "| Rank | Market | Ticker | Company | MarketCap | Status | Rating | Conviction | Score | AnalyzedOn |",
        "|------|--------|--------|---------|-----------|--------|--------|------------|-------|------------|",
    ]
    for rank, (market, tkr, name, cap) in enumerate(all_rows, 1):
        short_name = str(name)[:32]
        lines.append(
            f"| {rank} | {market} | {tkr} | {short_name} | {format_cap_usd(cap)} | pending | - | - | - | - |"
        )

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {len(all_rows)} rows to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
