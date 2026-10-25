# Can Random Stock Picking Be Profitable? A Test Using 11 Years of Stock Market Data

This package accompanies the LinkedIn article **"Can Random Stock Picking Be Profitable? A Test Using 11 Years of Stock Market Data"**. It tests the same random-stock rules as the October 2026 experiment, with **$50,000** starting capital, a **$1,000 maximum purchase**, and a **+5% intraday limit sell**. If the +5% target is not hit, the position remains open. We **count open positions at current marked value, including losses**, not just realized winners.

The actual historical test runs from **January 2015 through October 23, 2026**.

The article text and the annual comparison chart are included as `LINKEDIN_ARTICLE.md` and `linkedin_random_vs_spy_2015_2026_updated.png`.

## Installation (Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements_random_stock_2015_2026.txt
```

Python 3.10+ is recommended. Use a virtual environment if preferred.

## Run the test

1. Place the downloaded package contents together in a directory.
2. Download market prices. This is the long step and only needs to be done once; downloading is resumable:

```bash
python3 download_sp500_2015_2026.py
```

It uses **today's S&P 500 constituents**, Yahoo historical daily stock prices from **December 2014 through October 23, 2026**, plus SPY. Files are cached by batch under `sp500_historical_cache/` and consolidated as `downloaded_prices_2015_2026.csv.gz`. Yahoo may limit download requests; rerun the downloader if any batches fail.

3. Run the Monte Carlo backtest:

```bash
python3 random_stock_2015_2026.py \
  --data downloaded_prices_2015_2026.csv.gz \
  --capital 50000 --buy-limit 1000 --target 0.05 \
  --seeds 100 --out random_2015_2026_results
```

For **1,000 simulations per year, plus 1,000 continuous-path simulations**, change `--seeds 100` to `--seeds 1000`. This may require significant run time. For an existing full-coverage CSV, use `--data your_prices.csv`; required columns: `date,symbol,open,high,close`. Include SPY with `adj_close` for a dividend-adjusted SPY total-return benchmark.

4. Make charts from the real results (optional):

```bash
python3 plot_random_2015_2026.py --results random_2015_2026_results
```

## Outputs

- `summary_by_year.csv` — year, mean/median profit, 10th–90th percentiles, fraction profitable, max drawdown, fraction outperforming SPY.
- `trials_by_seed.csv` — full outcome of every seed in every year and one 2015–2026 continuous-account test.
- `equity_first_seed.csv` — daily equity (including losing open positions), cash, unsettled sale proceeds.
- `trades_first_seed.csv` — every completed trade for first random seed.
- `open_positions_first_seed.csv` — held shares, stale quotes, and unrealized losses for first seed.
- `settings.json` — experiment rules and limitations.
- `annual_return_vs_SPY.png`, `annual_profit_distribution.png` — charts after running the plot script.

Each **individual year** starts with **a new $50,000 account**. For example, 2022 begins with zero shares and $50,000 settled cash, independently of earlier years. The separate `continuous_2015_2026` run starts in 2015 and keeps the same holdings, cash, and pending settlements through 2026. The 2026 year is **year-to-date through October 23**, not a complete calendar year.

## Execution model

- Random stock choice is made from stocks quoted in the *previous* trading session; buying takes place at today's OPEN.
- Buy at most $1,000 per purchase (whole shares), with at most 50 open ticker positions.
- A +5% limit order sells when the day's HIGH reaches the target. A gap above target sells at the OPEN. Same-day entry and target execution are allowed. No other sell reason exists.
- No borrowing or repurchase cooldown; sale proceeds must **settle before they can be reinvested**. T+3 applies through September 4, 2017; T+2 until May 27, 2024; T+1 from May 28, 2024 onward.
- Realized and unrealized profit are separately included. Unsettled sale proceeds count toward portfolio equity but cannot fund purchases yet.

## Critical methodological limitations

**This is a preliminary research backtest, not evidence of a reliable trading advantage.**

**Survivorship bias:** The dataset contains current S&P 500 companies rather than the companies that belonged to the index at each historical date. Therefore, research based on this dataset is subject to survivorship bias. Companies that were removed from the index or delisted may be missing, which could overstate historical returns.

Quote gaps may also leave losing positions valued at an old reported price; `stale_positions_20sessions` reports this.

Other simplifications: no commissions, bid-ask spread, slippage, taxes, or dividend income for individual holdings. No intraday timestamp is available; an opening purchase followed by a target fill in the same day's HIGH is an idealized assumption. A +5% target may not fill in live trading even when the recorded HIGH equals the target. SPY adjusted-close comparison (when supplied) includes dividend adjustment, while the stock strategy does not. SPY annual returns use first-to-last **closing** quotes, whereas trading entries occur at the OPEN, causing a small window mismatch.

## Self-check

```bash
python3 test_random_stock_2015_2026.py
```

These tests use **synthetic prices** solely to check bookkeeping and dates; they are not genuine 2015–2026 market findings.

## Code authorship and copyright

**Development disclosure:** Developed by Andrei Akimov with assistance from OpenAI ChatGPT, including help with Python code, documentation, and tests.

Copyright (c) 2026 Andrei Akimov. This project is distributed under the **MIT License** (see [`LICENSE`](LICENSE)). You may use, copy, modify, redistribute, or use it commercially, provided the required copyright and license notices are preserved. The software is provided without warranty.

Third-party packages, externally sourced price data, index constituent lists, and other independently owned material are **not** relicensed by this project; their respective terms still apply. See `COPYRIGHT.txt`.

Code comments explain price data preparation, random stock selection, limit orders, settlement timing, portfolio valuation, annual resets, benchmark returns, charts, and synthetic tests.
