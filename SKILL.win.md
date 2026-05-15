---
name: trade
description: Run a TradingAgents-style multi-agent stock analysis live in the chat. The skill fetches market data, then has Claude role-play Market/Bull/Bear/Risk/Portfolio agents in a structured debate before producing a buy/sell/hold recommendation. Use when the user asks to "analyze", "trade", "evaluate", or "debate" a specific stock ticker (e.g. "/trade NVDA", "analyze TSLA", "should I buy AAPL"). Also supports `/trade portfolio` mode (reads portfolio.json and reviews all holdings + watchlist + cash plan) and `/trade screen` mode (advances the US 500 + TW 200 screening cycle by 50 tickers per round, then deep-dives the top 5 once all are scored). Do NOT use for general market commentary or non-equity asset analysis.
---

# /trade — multi-agent stock analysis

You are about to run a structured trading analysis on a single ticker, role-playing seven analyst personas in sequence. The user watches the full debate stream in chat.

## 1. Parse the request

Extract:
- **TICKER** — the stock symbol (uppercase). Required, EXCEPT when the user invokes portfolio mode.
- **DATE** — YYYY-MM-DD analysis date. Defaults to today. If the user says "yesterday" / "last Friday" / etc., resolve to an absolute date.

**Portfolio mode**: If the argument is the literal string `portfolio` (case-insensitive), skip the rest of this skill and run the Portfolio-mode flow in section 6 instead.

**Screen mode**: If the argument is the literal string `screen` (case-insensitive), skip the rest of this skill and run the Screen-mode flow in section 7 instead.

If TICKER is missing and mode is not `portfolio` or `screen`, ask the user once and stop.

## 2. Fetch market data

Run this command via the **PowerShell tool** (not Bash — the `$env:` prefix is PowerShell-only syntax; Bash returns exit code 127). The venv has all dependencies — do NOT pip-install anything:

```
$env:PYTHONIOENCODING="utf-8"; D:\MyCompany\TradingAgents\.venv\Scripts\python.exe D:\MyCompany\TradingAgents\scripts\fetch_report.py {TICKER} {DATE}
```

Read the full stdout. It contains five sections: price history, technical indicators, fundamentals, ticker news, macro news. **Do not echo the raw report back to the user** — they trust you to digest it. Summarise where useful inside each persona's section instead.

If the script errored (network, delisted ticker, future date with no data), stop and report the error.

## 3. Run the seven-persona debate

Output each persona as a `## <persona>` markdown section. Aim for **~400 words per persona** — substantive analysis, no filler. Each persona must engage with the prior arguments, not just restate independent views.

### 3.1 Market Analyst
Read the price + indicators. Comment on:
- Trend direction (50/200 SMA relationship, 10 EMA position)
- Momentum (MACD, RSI)
- Volatility / risk (ATR, Bollinger bands)
- Volume patterns
- A single-paragraph "what the chart says" verdict

### 3.2 Fundamentals & Sentiment Analyst
Read fundamentals + ticker news. Comment on:
- Valuation (PE, growth, margins) vs sector peers
- Recent earnings beats/misses if visible
- News narrative — positive/negative drivers in the past week
- Sentiment skew (bullish/bearish)
- Macro tie-in: one sentence from the macro section on relevant cross-currents

### 3.3 Bull Researcher — Round 1
Argue FOR a long position. Strongest evidence-based case. ~400 words.

### 3.4 Bear Researcher — Round 1
Argue AGAINST the long position. Rebut Bull Round 1's specific claims, not just generic risks. ~400 words.

### 3.5 Bull Researcher — Round 2
Rebut Bear Round 1. Concede valid points only when forced. Strengthen the bull thesis. ~400 words.

### 3.6 Bear Researcher — Round 2
Rebut Bull Round 2. Sharpest version of the bear case. ~400 words.

### 3.7 Research Manager
**Don't pick a side yet.** Synthesise the two-round debate into an investment plan:
- Which arguments held up under attack
- Which collapsed
- A draft thesis: directional bias + key catalysts + invalidation conditions
- Suggested position-sizing tilt (overweight / neutral / underweight)

### 3.8 Risk Debate — Aggressive / Conservative / Neutral (2 rounds each)
For each of the next 6 sections (Aggressive R1, Conservative R1, Neutral R1, Aggressive R2, Conservative R2, Neutral R2) write ~400 words. The three personas argue over Research Manager's draft thesis:

- **Aggressive** — pushes for larger position / leverage / longer hold; emphasises asymmetric upside
- **Conservative** — pushes for smaller size / tighter stops / shorter hold; emphasises tail risk
- **Neutral** — challenges both extremes; argues for the most expected-value-optimal sizing

Round 2 must directly attack Round 1 arguments from the other two, not just restate.

### 3.9 Portfolio Manager — Final Decision
Write **exactly this format** (rating MUST be one of BUY / SELL / HOLD in uppercase, on its own line near the top — the memory log parser depends on it):

```
RATING: BUY|SELL|HOLD

Position size: <e.g. 2% of portfolio | small starter | full conviction | none>
Time horizon: <e.g. 3-6 months | 1-2 weeks | long-term hold>
Entry: <e.g. market | limit at $X | wait for pullback to $Y>
Stop / invalidation: <price or condition that kills the thesis>
Take-profit / scale-out plan: <levels or rules>

Thesis (3-5 sentences): <what you believe and why>

Key risks accepted (2-3 bullets): <which bear/conservative concerns you are choosing to live with>
```

## 4. Append to the memory log

After the Portfolio Manager block, run this Bash command to append the decision to the long-term log (same file the Python TradingAgents pipeline uses). Replace placeholders. The HTML-comment separator is required.

```
$entry = @"
[{DATE} | {TICKER} | {RATING} | pending]

DECISION:
{full_portfolio_manager_block_verbatim}

<!-- ENTRY_END -->

"@
$logPath = "$env:USERPROFILE\.tradingagents\memory\trading_memory.md"
New-Item -ItemType Directory -Path (Split-Path $logPath) -Force | Out-Null
Add-Content -Path $logPath -Value $entry -Encoding UTF8
```

Idempotency: before appending, read the log and skip if a pending entry for the same date+ticker already exists.

## 5. Wrap up

End with a one-line summary line like:
`Done. Logged to ~/.tradingagents/memory/trading_memory.md. Run /trade reflect <TICKER> <DATE> after the move to score this call.`

(The `reflect` subcommand is not yet implemented — mention it only as a future hook.)

---

## Style rules for the whole debate

- **No emojis. No headers beyond what this skill specifies.**
- Each persona writes in first person ("I see…", "My concern is…") to make the debate feel real.
- Cite specific numbers from the data report whenever possible — vague is useless.
- If the data fetch returned partial data (some sections errored), say so in the relevant persona's section and lower confidence accordingly rather than fabricating.
- Output language: English. (The data and persona-style rhetoric work best in English; the user can ask for a Chinese summary at the end if needed.)
- If the user interrupts mid-debate to redirect ("Bull, you missed X"), incorporate the feedback into the next persona's turn rather than restarting.

---

## 6. Portfolio mode (`/trade portfolio`)

Triggered when the argument is the literal `portfolio`. This is a different flow — compressed per-ticker analysis plus a portfolio-level synthesis. Aim total output around 3000-5000 words, NOT the full 7-persona debate per ticker.

### 6.1 Load the portfolio file

Read `D:\MyCompany\TradingAgents\portfolio.json`. It contains:
- `stocks[]` — list of {ticker, shares, cost_basis_per_share, notes}
- `bonds[]` — list of fixed-income holdings (metadata only, no analysis)
- `cash_usd` — uninvested cash
- `watchlist[]` — tickers the user is considering for new money
- `constraints{}` — max_single_stock_pct, min_cash_reserve_usd, tax_lot_method, account_type

If the file is missing or malformed, stop and report. Do not fabricate holdings.

### 6.2 Fetch data for every stock + every watchlist ticker

Run `fetch_report.py` for each ticker in `stocks[]` and `watchlist[]`, ONE AT A TIME using the PowerShell tool (NOT Bash — the `$env:` prefix is PowerShell syntax). Sequential fetching avoids yfinance rate-limit cascades. Use today's date unless the user specified otherwise.

If any single fetch errors, continue with the rest; mark that ticker as "data unavailable" in its section.

### 6.3 Per-holding analysis (~250 words each)

For each stock in `stocks[]`, write a compact section with this exact structure:

```
## <TICKER> — <Company short name>

Current: $<price> | Cost: $<cost_basis> | P/L: <±%> | Shares: <n> | Market Value: $<mv>

Read (3-4 sentences combining technicals + fundamentals + news that actually move the needle):
<analysis>

Rating: BUY | SELL | HOLD | TRIM | ADD
Action: <one specific actionable, e.g. "Limit buy 1 share at $218" or "Sell market" or "Hold, no add above $400">
Stop / invalidation: <price level + condition>
```

Do not run the full 7-persona debate. Compress to a single integrated analyst voice. If a holding genuinely warrants the full debate (e.g. user explicitly asked, or it's a high-conviction decision point), call that out and offer to run `/trade <TICKER>` separately.

### 6.4 Watchlist scan (~150 words each)

For each ticker in `watchlist[]`, write an even shorter section:

```
## <TICKER> — watchlist

Current: $<price>

Verdict (2-3 sentences):
<is this a good place to deploy fresh cash now? if not now, at what price?>

Action: WAIT | BUY NOW | SKIP
Entry zone: $<price range> or "skip — better elsewhere"
```

### 6.5 Portfolio-level synthesis

After all per-ticker sections, write a `## Portfolio Synthesis` block covering:

- **Allocation snapshot**: stocks / bonds / cash percentages, total portfolio value
- **Concentration**: largest single-name %, sector concentration (esp. AI/semi cluster), correlation risk
- **Constraint checks**: any `constraints{}` violations (e.g., cash below min reserve, single stock above max pct)
- **Cash deployment plan**: given the current cash, what specific dollar amounts go where? Be concrete — "deploy $2,500 to NVDA at $218 if reached, $2,000 to TSM at $395, hold $4,000 as reserve."
- **Bond commentary**: one sentence on the fixed-income holding. If duration/credit risk is meaningfully off for the user's setup, flag it. Otherwise just note "holding through maturity, no action."

### 6.6 Actionable checklist

End with a `## Action Checklist` — a flat numbered list of concrete orders to place, in priority order. Each item must include: order type (market/limit/stop), ticker, price, quantity, and rationale-in-one-clause. Example:

```
1. SELL 4 GIS market — tax-loss harvest, redeploy capital.
2. LIMIT BUY 1 NVDA @ $218 — first add per active thesis.
3. LIMIT BUY 1 TSM @ $395 — first add per active thesis.
4. No action on GOOGL — hold; wait for $370 zone.
```

### 6.7 Memory log entry

Append ONE entry to `~/.tradingagents/memory/trading_memory.md` with this format (different from per-ticker format):

```
[YYYY-MM-DD | PORTFOLIO | summary | pending]

PORTFOLIO REVIEW:
- Total value: $X
- Allocation: stocks X%, bonds X%, cash X%
- Key actions: <bulleted list, max 5>
- Constraint flags: <any violations, or "none">

<!-- ENTRY_END -->
```

Idempotency: skip if a `PORTFOLIO` entry for today's date already exists pending.

### 6.8 Wrap-up

End with: `Portfolio review logged. Update portfolio.json when you place orders or positions change.`

---

## 7. Screen mode (`/trade screen`)

Triggered when the argument is the literal `screen`. Advances the US 500 + TW 200 screening cycle by ONE round (10 tickers per round, fetched sequentially). When all rows are scored, automatically runs the Top-5 deep-dive on the next invocation.

### 7.1 Load universe state

Read `D:\MyCompany\TradingAgents\universe\universe.md`. It contains a markdown table with columns:
`Rank | Market | Ticker | Company | MarketCap | Status | Rating | Conviction | Score | AnalyzedOn`

`Market` is either `US` or `TW`. The universe contains roughly 500 US + 200 TW = 700 rows total.

Count rows by status:
- If any rows have `Status=pending` → go to section 7.2 (normal round)
- If ALL rows have `Status=done` AND no Top-5 deep-dive has been run since the last refresh → go to section 7.3 (top-5 final)
- If the cycle is fully complete (top-5 done) → tell user to run `refresh_universe.py` to start a new cycle, and stop

If the file is missing, instruct user to run `D:\MyCompany\TradingAgents\scripts\refresh_universe.py` first, and stop.

### 7.2 Normal round — analyze next 10 pending, sequentially

Pick the 10 lowest-rank `pending` rows (i.e., highest market cap that hasn't been analyzed yet).

**Fetch SEQUENTIALLY, not in parallel.** yfinance rate-limits aggressively when hit with many concurrent calls, and parallel fetching has consistently triggered 429s in past runs. One ticker at a time, in order.

**Use the PowerShell tool, NOT Bash.** The fetch command uses PowerShell `$env:` syntax which Bash cannot parse (exit code 127). For each ticker, issue:

```
$env:PYTHONIOENCODING="utf-8"; D:\MyCompany\TradingAgents\.venv\Scripts\python.exe D:\MyCompany\TradingAgents\scripts\fetch_report.py {TICKER} {DATE}
```

For TW tickers, pass the full Yahoo symbol including `.TW` suffix.

For each ticker, after the fetch returns, immediately write its analysis section before moving to the next fetch. Workflow per ticker: fetch → analyze → write section → update universe.md row → next ticker. This means one PowerShell call and one Edit call per ticker, never batched.

If a fetch errors (network, delisted, rate-limited), mark that row's Status as `skip` with note `error:<short reason>` in AnalyzedOn, and continue to the next ticker. Do not abort the round.

Each analysis section is ~200-300 words, single integrated analyst voice, NOT full 7-persona:

```
## <RANK>. <MARKET>:<TICKER> — <Company>

Snapshot: Price | 50 SMA | 200 SMA | RSI | Forward PE | Market Cap

Read: <3-5 sentences combining technicals, valuation, recent news. Be specific with numbers.>

Rating: BUY | BUY-on-pullback | HOLD | TRIM | SELL
Conviction: 1-5 (where 5 = high confidence in the rating)
Score: <rating_value × conviction, where BUY=+2, BUY-on-pullback=+1, HOLD=0, TRIM=-1, SELL=-2>
One-liner action: <e.g. "Add at $X" / "Hold, no action" / "Avoid, no edge here">
```

For TW stocks, prefix prices with `NT$` not `$`. Note that news quality for TW small-caps may be thin via yfinance — if so, weight technicals + valuation more heavily and lower Conviction accordingly. Don't fabricate news coverage.

Update `universe.md` after EACH ticker (not in a single batch at end), so progress survives interruption. Use the Edit tool with `replace_all: false` and the unique row string as the match.

### 7.3 Top-5 deep-dive

Triggered when all rows have `Status=done`. Take the 5 highest-Score rows (ties broken by higher market cap).

For these 5 tickers, run the FULL 7-persona debate (section 3) — same as a regular `/trade <TICKER>` call. The cost is justified because these are the decision-grade candidates for fresh capital deployment.

After all 5 debates, write a `## Final Allocation Recommendation` block:
- Rank the 5 from best to worst risk-adjusted opportunity
- Concrete dollar allocation from the user's available cash (read `portfolio.json` → `cash_usd` minus `constraints.min_cash_reserve_usd`)
- Specific entry orders for each
- Diversification check against existing holdings — if a top-5 candidate is already a heavy position, deprioritize

Append a single `[YYYY-MM-DD | SCREEN-TOP5 | <tickers> | pending]` entry to the memory log with the full recommendation.

### 7.4 Wrap-up

For a normal round (7.2): end with `Round complete. N/M analyzed (M = total rows in universe.md). Run /trade screen again to continue.` (Compute N from the updated file.)

For the top-5 round (7.3): end with `Cycle complete. Top-5 deep-dive logged. Run refresh_universe.py to start a new cycle.`

### 7.5 Idempotency and interruption

- If the user re-runs `/trade screen` mid-round, just continue with the next 10 pending. The previously-analyzed batch is preserved by the `done` status.
- If a data fetch errors for one ticker in a round, mark that single row's Status as `skip` with a brief note in AnalyzedOn (`error:<reason>`), continue the rest, don't abort the round.
