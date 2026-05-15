"""Fetch a single ticker's market data, indicators, fundamentals, and news
as one markdown report, for consumption by the /trade Claude Code Skill.

Output goes to stdout. Designed to be invoked as:

    python scripts/fetch_report.py NVDA 2026-05-14

The date defaults to today if omitted. Data source: yfinance (no API key
required). Reuses the project's existing dataflow wrappers so any future
data-vendor switch (e.g. Alpha Vantage) keeps the Skill's output stable.
"""

from __future__ import annotations

import io
import sys
from datetime import datetime, timedelta

# Force UTF-8 on stdout/stderr so non-ASCII (Chinese ticker news, em-dashes,
# accented company names) doesn't crash under Windows' default cp950 codec.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from tradingagents.dataflows.y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals,
)
from tradingagents.dataflows.yfinance_news import (
    get_news_yfinance,
    get_global_news_yfinance,
)

# Headline indicators — keep the set tight so the report stays scannable
# rather than wallpaper-thick.
_INDICATORS = ["close_50_sma", "close_200_sma", "close_10_ema", "macd", "rsi", "boll", "atr"]
_PRICE_LOOKBACK_DAYS = 90
_INDICATOR_LOOKBACK_DAYS = 30
_NEWS_LOOKBACK_DAYS = 7


def _section(title: str, body: str) -> str:
    return f"\n## {title}\n\n{body.strip()}\n"


def main(ticker: str, curr_date: str) -> None:
    end = datetime.strptime(curr_date, "%Y-%m-%d")
    price_start = (end - timedelta(days=_PRICE_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    news_start = (end - timedelta(days=_NEWS_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    parts: list[str] = [f"# Market Data Report — {ticker} as of {curr_date}\n"]

    try:
        price = get_YFin_data_online(ticker, price_start, curr_date)
        parts.append(_section(f"Price history ({_PRICE_LOOKBACK_DAYS}d)", price))
    except Exception as e:
        parts.append(_section(f"Price history ({_PRICE_LOOKBACK_DAYS}d)", f"[ERROR] {e}"))

    indicator_lines = []
    for ind in _INDICATORS:
        try:
            row = get_stock_stats_indicators_window(ticker, ind, curr_date, _INDICATOR_LOOKBACK_DAYS)
            indicator_lines.append(f"### {ind}\n{row}\n")
        except Exception as e:
            indicator_lines.append(f"### {ind}\n[ERROR] {e}\n")
    parts.append(_section(f"Technical indicators ({_INDICATOR_LOOKBACK_DAYS}d window)", "\n".join(indicator_lines)))

    try:
        fundamentals = get_fundamentals(ticker, curr_date)
        parts.append(_section("Fundamentals", fundamentals))
    except Exception as e:
        parts.append(_section("Fundamentals", f"[ERROR] {e}"))

    try:
        news = get_news_yfinance(ticker, news_start, curr_date)
        parts.append(_section(f"Ticker news (past {_NEWS_LOOKBACK_DAYS}d)", news))
    except Exception as e:
        parts.append(_section(f"Ticker news (past {_NEWS_LOOKBACK_DAYS}d)", f"[ERROR] {e}"))

    try:
        macro = get_global_news_yfinance(curr_date)
        parts.append(_section(f"Macro / global news (past {_NEWS_LOOKBACK_DAYS}d)", macro))
    except Exception as e:
        parts.append(_section(f"Macro / global news (past {_NEWS_LOOKBACK_DAYS}d)", f"[ERROR] {e}"))

    sys.stdout.write("".join(parts))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write("usage: fetch_report.py <TICKER> [YYYY-MM-DD]\n")
        sys.exit(2)
    ticker = sys.argv[1].upper()
    curr_date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")
    main(ticker, curr_date)
