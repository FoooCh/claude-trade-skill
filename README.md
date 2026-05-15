# claude-trade-skill

A [Claude Code](https://docs.claude.com/en/docs/claude-code) skill that runs a multi-agent trading debate (Market analyst → Bull/Bear → Risk debate → Portfolio Manager) on US and Taiwan-listed stocks. Inspired by [TradingAgents](https://github.com/TauricResearch/TradingAgents) and built as a thin layer on top of its data pipeline.

## Three modes

| Command | What it does |
|---|---|
| `/trade NVDA` | Full 7-persona debate on a single ticker. Outputs BUY / SELL / HOLD with sizing, stop, take-profit. |
| `/trade portfolio` | Reads your `portfolio.json`, runs compressed analysis on every holding + watchlist, prints a cash-deployment plan. |
| `/trade screen` | Advances the US 500 + TW 200 screening cycle by one round (10 tickers). When the full cycle is done, automatically triggers a deep-dive on the top-5 scorers. Pair with `/loop 15m /trade screen` for unattended cycles. |

Every decision is appended to `~/.tradingagents/memory/trading_memory.md` for later review.

## Prerequisites

This skill is a thin layer on top of [TradingAgents](https://github.com/TauricResearch/TradingAgents). Install that first:

```bash
git clone https://github.com/TauricResearch/TradingAgents.git ~/TradingAgents
cd ~/TradingAgents
python -m venv .venv
# Windows PowerShell:  .\.venv\Scripts\Activate.ps1
# macOS / Linux bash:  source .venv/bin/activate
pip install -e .
```

Verify the data layer imports:

```bash
python -c "from tradingagents.dataflows.y_finance import get_YFin_data_online; print('ok')"
```

You also need [Claude Code](https://docs.claude.com/en/docs/claude-code) installed and authenticated.

## Install this skill

```bash
git clone git@github.com:FoooCh/claude-trade-skill.git ~/claude-trade-skill
cd ~/claude-trade-skill
```

### 1. Install the skill file

Pick the variant that matches your OS:

```bash
# macOS / Linux:
mkdir -p ~/.claude/skills/trade
cp SKILL.mac.md ~/.claude/skills/trade/SKILL.md

# Windows PowerShell:
mkdir $HOME\.claude\skills\trade -Force
cp SKILL.win.md $HOME\.claude\skills\trade\SKILL.md
```

Open the installed `SKILL.md` and adjust hardcoded paths if your TradingAgents lives somewhere other than `~/TradingAgents` (macOS) or `D:\MyCompany\TradingAgents` (Windows).

### 2. Copy the data scripts into TradingAgents

`fetch_report.py` and `refresh_universe.py` need to live inside your TradingAgents checkout so they can import from `tradingagents.dataflows`:

```bash
cp scripts/fetch_report.py ~/TradingAgents/scripts/fetch_report.py
cp scripts/refresh_universe.py ~/TradingAgents/scripts/refresh_universe.py
```

### 3. Create your portfolio file

```bash
cp portfolio.example.json ~/TradingAgents/portfolio.json
# edit ~/TradingAgents/portfolio.json with your real holdings
```

`portfolio.json` is gitignored — it should never leave your machine.

### 4. Generate the screening universe

```bash
~/TradingAgents/.venv/bin/python ~/TradingAgents/scripts/refresh_universe.py
```

This takes ~15-20 minutes (it queries yfinance for market cap on ~1500 tickers with throttling). It writes `~/TradingAgents/universe/universe.md`. Re-run weekly.

### 5. Try it

```
/trade NVDA              # single-ticker deep dive
/trade portfolio         # holdings review
/trade screen            # one screening round
/loop 15m /trade screen  # automated cycle (Claude Code runs this every 15 min until done)
```

## Data sources

Right now: **yfinance only** (price, indicators, fundamentals, news). Limitations:

- Yahoo rate-limits aggressively; `refresh_universe.py` has throttle + retry but may still miss some tickers.
- Taiwan small-cap news via yfinance is sparse — analysis weights technicals + valuation more heavily for these. The skill is instructed not to fabricate news coverage when it's thin.

Future hooks (not yet implemented): FinMind for richer Taiwan data, Finnhub for friendlier US news limits, tradingview-ta for a 30-indicator consensus signal.

## Layout

```
claude-trade-skill/
├── README.md                 # you are here
├── .gitignore
├── SKILL.mac.md              # macOS / Linux variant
├── SKILL.win.md              # Windows variant
├── portfolio.example.json    # template — copy to portfolio.json
└── scripts/
    ├── refresh_universe.py   # weekly: rebuild universe.md
    └── fetch_report.py       # per-ticker data fetch (used by the skill)
```

## License

Private repo for personal use. TradingAgents is Apache-2.0 (see upstream).
