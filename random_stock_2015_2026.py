#!/usr/bin/env python3
# Copyright (c) 2026 Andrei Akimov.
# SPDX-License-Identifier: MIT
# Licensed under the MIT License; see LICENSE for details.
# Developed by Andrei Akimov with assistance from OpenAI ChatGPT.

"""Random-stock Monte Carlo backtest, 2015–2026; annual reset and continuous.

Input: long CSV/CSV.GZ/Parquet with date,symbol,open,high,close
Optional: adj_close for SPY buy-and-hold total-return benchmark.

Matches the core 2024–2026 random strategy:
 - daily random purchases from tickers visible on the PREVIOUS trading session
 - buy at current OPEN, <= $1,000 of whole shares, settled cash only
 - at most 50 holdings / one holding per ticker
 - sell at +5% if same-day HIGH touches limit; gap-through filled at OPEN
 - otherwise hold losses indefinitely, mark them to last reported CLOSE
 - T+3 until 2017-09-04, T+2 from 2017-09-05 through 2024-05-27,
   T+1 from 2024-05-28; sale proceeds counted in equity but not buying cash
 - no commissions, slippage, dividends on individual positions, taxes,
   point-in-time S&P 500 membership, or delisting adjustments.

The 2015..2026 inclusive yearly-reset runs each begin with new $50k.
Additionally a continuous account begins once in 2015 and is carried forward.

Examples:
  python3 random_stock_2015_2026.py --data downloaded_prices_2015_2026.csv.gz
  python3 random_stock_2015_2026.py --data downloaded_prices.csv --seeds 1000
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

START_DEFAULT = '2015-01-01'
END_DEFAULT = '2026-10-23'
TRADE_FIELDS = ['period', 'seed', 'symbol', 'buy_date', 'sell_date', 'shares',
                'buy_price', 'sell_price', 'cost', 'proceeds', 'profit']


def read_prices(path: Path) -> pd.DataFrame:
    """Load and normalize one long-form historical daily-price file.

    Required columns: date, symbol, open, high, close. Optional adj_close
    is used only for the SPY comparison, not individual-stock execution.
    Rows with unusable prices are dropped rather than fabricated.
    """
    if not path.is_file():
        raise FileNotFoundError(f'{path} does not exist. Run the companion price downloader first.')
    if path.suffix.lower() in ('.parquet', '.pq'):
        d = pd.read_parquet(path)
    else:
        d = pd.read_csv(path)
    d.columns = [str(c).strip().lower().replace(' ', '_') for c in d.columns]
    d = d.rename(columns={'ticker': 'symbol', 'datetime': 'date', 'adjclose': 'adj_close', 'adjusted_close': 'adj_close'})
    needed = {'date', 'symbol', 'open', 'high', 'close'}
    if needed - set(d.columns):
        raise ValueError(f'Input must contain {sorted(needed)}; got {list(d.columns)}')
    keep = ['date', 'symbol', 'open', 'high', 'close'] + (['adj_close'] if 'adj_close' in d.columns else [])
    d = d[keep].copy()
    d['date'] = pd.to_datetime(d.date, utc=True, errors='coerce').dt.tz_localize(None).dt.normalize()
    d['symbol'] = d.symbol.astype(str).str.strip().str.upper().str.replace('.', '-', regex=False)
    for c in ['open', 'high', 'close'] + (['adj_close'] if 'adj_close' in d.columns else []):
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d.dropna(subset=['date', 'symbol', 'open', 'high', 'close'])
    d = d[(d.open > 0) & (d.close > 0) & (d.high + 1e-8 >= d.open) & (d.high + 1e-8 >= d.close)]
    return d.sort_values(['date','symbol']).drop_duplicates(['date','symbol'],keep='last').reset_index(drop=True)


def build_panel(df: pd.DataFrame, start: str, end: str):
    """Convert quotes to aligned day-by-stock arrays for faster repeated runs.

    SPY defines exchange sessions when present and is excluded from the
    universe available to the randomized stock-selection algorithm.
    The extra pre-start date supports yesterday-only eligibility.
    """
    # A prior quote before first trade date (e.g. Dec 2014) is useful and never
    # allows trades using future stock membership/price information.
    begin = pd.Timestamp(start)
    stop = pd.Timestamp(end)
    d = df[df.date <= stop]
    if d.empty:
        raise ValueError(f'No valid prices on or before {stop.date()}')
    # SPY dates anchor US sessions if present; otherwise use union of dates.
    spy = d[d.symbol == 'SPY'].set_index('date').sort_index()
    cal = spy.index[(spy.index >= begin) & (spy.index <= stop)] if len(spy) else pd.DatetimeIndex(sorted(d.loc[(d.date >= begin) & (d.date <= stop), 'date'].unique()))
    if len(cal) == 0:
        raise ValueError(f'No stock quotes in {start}..{end}')
    cols = sorted(set(d.symbol.unique()) - {'SPY'})
    # It is NOT sufficient to use the previous calendar day: need last actual
    # dataset trading session before the requested first period date.
    pre = d.loc[d.date < cal[0], 'date']
    prior_day = pre.max() if len(pre) else None
    all_dates = pd.DatetimeIndex([prior_day]).append(cal) if prior_day is not None else cal
    trad = d[d.symbol != 'SPY']
    trad = trad[(trad.date >= all_dates[0]) & (trad.date <= all_dates[-1])]
    matrices = {}
    for field in ('open', 'high', 'close'):
        p = trad.pivot(index='date', columns='symbol', values=field)
        matrices[field] = p.reindex(index=all_dates, columns=cols).to_numpy(dtype=np.float64)
    # Only actual price quotes can qualify. We have no current-day knowledge
    # in yesterday's selection pool: eligibility uses prev-day quote only.
    op, hi, cl = matrices['open'], matrices['high'], matrices['close']
    valid = np.isfinite(op) & np.isfinite(hi) & np.isfinite(cl) & (op > 0) & (cl > 0) & (hi + 1e-8 >= np.maximum(op, cl))
    spy_bench = pd.DataFrame(index=cal)
    if len(spy):
        for f in ('close', 'adj_close'):
            if f in spy.columns:
                spy_bench[f] = spy[f].reindex(cal)
    return all_dates, cal, cols, op, hi, cl, valid, spy_bench


def lag_for_day(day: pd.Timestamp) -> int:
    """US equity settlement delay in *trading sessions* on sale date.

    T+3 before Sep 5, 2017; T+2 until May 27, 2024; T+1 afterward.
    The main loop indexes exchange sessions, not calendar days.
    """
    if day < pd.Timestamp('2017-09-05'):
        return 3
    if day < pd.Timestamp('2024-05-28'):
        return 2
    return 1


def simulate(indices: np.ndarray, dates: pd.DatetimeIndex,
             symbols: list[str], op: np.ndarray, hi: np.ndarray,
             cl: np.ndarray, valid: np.ndarray,
             *, capital: float, buy_limit: float, target: float, seed: int,
             period: str, keep_details: bool = False):
    """Simulate one independently seeded portfolio on selected sessions.

    All dollar figures include settled and unsettled cash where appropriate.
    When keep_details is false, omit large per-trade/per-day output to
    keep 1,000-run Monte Carlo sweeps economical.
    """
    rng = np.random.default_rng(seed)
    n = len(symbols)
    cash = float(capital)
    positions_shares = np.zeros(n, dtype=np.int64)
    positions_buy = np.zeros(n, dtype=np.float64)
    positions_date = np.full(n, -1, dtype=np.int32)
    latest_close = np.full(n, np.nan, dtype=np.float64)
    latest_day = np.full(n, -1, dtype=np.int32)
    pending: dict[int, float] = {}  # calendar index of settlement -> dollars
    closed_profit = 0.0
    buys = sells = 0
    # Nominal maximum count of positions: 50 for $50k / $1k.
    # Because whole-share purchases can cost less than $1k, cash remains unused.
    max_slots = int(capital // buy_limit)
    prior_peak = float(capital)
    max_drawdown = 0.0
    equity_curve, trades = [], []
    first_day, last_day = int(indices[0]), int(indices[-1])
    for i in indices:
        i = int(i)
        day = dates[i]
        # Sale proceeds cannot fund purchases until the settlement session.
        # Until then they still count toward economic account equity.
        cash += pending.pop(i, 0.0)
        # Update marked-to-market prices only for stocks with valid quotes.
        # A missing/delisted stock may retain a stale quote: a major bias.
        today_valid = valid[i]
        today = today_valid & np.isfinite(cl[i])
        latest_close[today] = cl[i, today]
        latest_day[today] = i

        # First eligible day uses the last session before period start, if any.
        previous = valid[i - 1] if i > 0 else np.zeros(n, dtype=bool)
        # BUY phase: stock eligibility is determined by the prior session.
        # We check today's opening quote only to decide whether the order
        # is executable, not to select candidates using future information.
        if cash + 1e-8 >= buy_limit and np.count_nonzero(positions_shares) < max_slots:
            pool = np.flatnonzero(previous & (positions_shares == 0))
            # Original algorithm randomly permutes the complete prior-day pool.
            for j in rng.permutation(pool):
                if cash + 1e-8 < buy_limit or np.count_nonzero(positions_shares) >= max_slots:
                    break
                if not today_valid[j]:
                    continue
                price = op[i, j]
                # Buy whole shares; no margin and no fractional shares.
                shares = int(np.floor((buy_limit + 1e-8) / price))
                if shares <= 0:
                    continue
                cost = shares * price
                if cost > cash + 1e-8:
                    continue
                positions_shares[j] = shares
                positions_buy[j] = price
                positions_date[j] = i
                cash -= cost
                buys += 1

        # SELL phase: idealized standing limit order at 5% above entry.
        # If the daily high reaches it, assume a fill at the limit price
        # (or the open if the stock gaps above the limit).
        # Includes same-day fills after a buy, but daily OHLC bars cannot
        # verify intraday ordering or guarantee actual limit execution.
        active = np.flatnonzero((positions_shares > 0) & today_valid)
        for j in active:
            goal = positions_buy[j] * (1.0 + target)
            if hi[i, j] + 1e-9 < goal:
                continue
            exit_price = max(goal, op[i, j])
            proceeds = positions_shares[j] * exit_price
            gain = proceeds - positions_shares[j] * positions_buy[j]
            # Schedule proceeds for a later exchange session.
            settle_idx = i + lag_for_day(day)
            pending[settle_idx] = pending.get(settle_idx, 0.0) + proceeds
            closed_profit += gain
            if keep_details:
                trades.append({'period': period, 'seed': seed, 'symbol': symbols[j],
                    'buy_date': dates[positions_date[j]].date().isoformat(),
                    'sell_date': day.date().isoformat(), 'shares': int(positions_shares[j]),
                    'buy_price': round(float(positions_buy[j]), 5),
                    'sell_price': round(float(exit_price), 5),
                    'cost': round(float(positions_shares[j] * positions_buy[j]), 2),
                    'proceeds': round(float(proceeds), 2), 'profit': round(float(gain), 2)})
            positions_shares[j] = 0
            positions_buy[j] = 0
            positions_date[j] = -1
            sells += 1
        # ACCOUNT EQUITY = settled cash + unsettled sale proceeds
        #                  + marked value of still-open positions.
        # This includes floating losses: realized profits alone are misleading.
        active = positions_shares > 0
        prices = np.where(np.isfinite(latest_close), latest_close, positions_buy)
        market_value = float(np.dot(positions_shares, prices))
        floating = float(np.dot(positions_shares, prices - positions_buy))
        unsettled = float(sum(pending.values()))
        equity = cash + unsettled + market_value
        # Independent reconciliation catches missing cash or double-counted P/L.
        if not np.isclose(equity, capital + closed_profit + floating, atol=1e-4):
            raise AssertionError('Portfolio reconciliation failed')
        prior_peak = max(prior_peak, equity)
        max_drawdown = min(max_drawdown, (equity / prior_peak - 1.0) * 100.0)
        if keep_details:
            equity_curve.append({'period': period, 'seed': seed, 'date': day.date().isoformat(),
                'equity': round(equity, 2), 'cash': round(cash, 2),
                'unsettled': round(unsettled, 2), 'stock_value': round(market_value, 2),
                'closed_profit_cumulative': round(closed_profit, 2),
                'unrealized_profit': round(floating, 2),
                'positions': int(np.count_nonzero(active))})
    open_idx = np.flatnonzero(positions_shares)
    unrealized = float(np.dot(positions_shares, prices - positions_buy))
    # Diagnose assets with no quote for >=20 sessions, e.g. delisted stocks.
    # They remain valued at last seen close; this can overstate results.
    stale = int(np.count_nonzero((positions_shares > 0) & ((last_day - latest_day) >= 20)))
    summary = dict(period=period, seed=seed,
        start=dates[first_day].date().isoformat(), end=dates[last_day].date().isoformat(),
        sessions=len(indices), starting_capital=capital, buys=buys, sells=sells,
        realized_profit=round(closed_profit, 2), unrealized_profit=round(unrealized, 2),
        total_profit=round(equity-capital, 2), equity=round(equity, 2),
        return_pct=round((equity/capital-1)*100, 5),
        max_drawdown_pct=round(max_drawdown, 5),
        open_positions=len(open_idx), stale_positions_20sessions=stale,
        settled_cash=round(cash, 2), unsettled_cash=round(unsettled, 2))
    holding_rows = []
    if keep_details:
        for j in open_idx:
            holding_rows.append({'period':period,'seed':seed,'symbol':symbols[j],
                'buy_date':dates[positions_date[j]].date().isoformat(),
                'shares':int(positions_shares[j]),'buy_price':round(float(positions_buy[j]),5),
                'last_close':round(float(prices[j]),5),
                'unrealized':round(float(positions_shares[j]*(prices[j]-positions_buy[j])),2),
                'sessions_since_last_quote':int(last_day-latest_day[j])})
    return summary, equity_curve, trades, holding_rows


def spy_period_return(spy_bench: pd.DataFrame, first: pd.Timestamp, last: pd.Timestamp) -> tuple[float, str]:
    """Calculate SPY buy/hold period return using adjusted close if present.

    The return is first-close to last-close, so it has a small timing
    mismatch with the active strategy's opening-price purchases.
    """
    if spy_bench.empty:
        return np.nan, 'unavailable'
    s = spy_bench.loc[first:last]
    typ = 'adj_close' if 'adj_close' in s and s.adj_close.notna().sum() >= 2 else 'close'
    if typ not in s:
        return np.nan, 'unavailable'
    s = s[typ].dropna()
    if len(s) < 2 or s.iloc[0] <= 0:
        return np.nan, 'unavailable'
    return round((float(s.iloc[-1])/float(s.iloc[0])-1)*100, 5), 'SPY_adj_close' if typ=='adj_close' else 'SPY_price_only'


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize per-seed distributions; avoid reporting only winners.

    Includes negative outcomes, mean drawdown, and fraction beating SPY.
    """
    rows=[]
    for period, sub in df.groupby('period',sort=False):
        bench = float(sub.benchmark_pct.iloc[0]) if pd.notna(sub.benchmark_pct.iloc[0]) else float('nan')
        rows.append(dict(period=period, start=sub.start.iloc[0], end=sub.end.iloc[0],
            number_simulations=len(sub), start_capital=float(sub.starting_capital.iloc[0]),
            mean_profit=round(sub.total_profit.mean(), 2), median_profit=round(sub.total_profit.median(),2),
            p10_profit=round(sub.total_profit.quantile(.10),2), p90_profit=round(sub.total_profit.quantile(.90),2),
            worst_profit=round(sub.total_profit.min(),2), best_profit=round(sub.total_profit.max(),2),
            mean_return_pct=round(sub.return_pct.mean(),3), median_return_pct=round(sub.return_pct.median(),3),
            profitable_pct=round((sub.total_profit>0).mean()*100,2),
            mean_max_drawdown_pct=round(sub.max_drawdown_pct.mean(),3),
            worst_max_drawdown_pct=round(sub.max_drawdown_pct.min(),3),
            mean_realized_profit=round(sub.realized_profit.mean(),2),
            mean_unrealized_profit=round(sub.unrealized_profit.mean(),2),
            mean_open_positions=round(sub.open_positions.mean(),2),
            pct_with_stale_holdings=round((sub.stale_positions_20sessions>0).mean()*100,2),
            spy_return_pct=bench, benchmark_type=sub.benchmark_type.iloc[0],
            beat_spy_pct=round((sub.return_pct>bench).mean()*100,2) if np.isfinite(bench) else np.nan))
    return pd.DataFrame(rows)


def main():
    """Run independent year resets and a separate continuous account."""
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--data',default='downloaded_prices_2015_2026.csv.gz')
    p.add_argument('--start',default=START_DEFAULT)
    p.add_argument('--end',default=END_DEFAULT)
    p.add_argument('--capital',type=float,default=50000.0)
    p.add_argument('--buy-limit',type=float,default=1000.0)
    p.add_argument('--target',type=float,default=0.05)
    p.add_argument('--seeds',type=int,default=100)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--out',default='random_2015_2026_results')
    p.add_argument('--allow-partial',action='store_true',
                   help='Allow missing requested years (not suitable for full 2015–2026 study)')
    a=p.parse_args()
    if min(a.capital,a.buy_limit)<=0 or a.capital<a.buy_limit or not (0<a.target<1) or a.seeds<1:
        p.error('Require capital>=buy-limit>0, 0<target<1, and seeds>=1')
    d=read_prices(Path(a.data))
    dates,cal,symbols,op,hi,cl,valid,spy=build_panel(d,a.start,a.end)
    print(f'Input: {len(d):,} quotes, {len(symbols)} stocks, {cal.min().date()}..{cal.max().date()}, SPY benchmark: {not spy.empty}',flush=True)
    required=set(range(pd.Timestamp(a.start).year, pd.Timestamp(a.end).year+1))
    missing=sorted(required-set(cal.year))
    if missing and not a.allow_partial:
        raise ValueError(f'Missing historical years {missing}; download older prices with the companion downloader. '
                         'Use --allow-partial only if you deliberately want an incomplete test.')
    if missing:
        print(f'WARNING: missing years {missing}; these results are INCOMPLETE.',flush=True)
    if cal.min().date() > pd.Timestamp(a.start).date()+pd.Timedelta(days=10) or cal.max().date() < pd.Timestamp(a.end).date()-pd.Timedelta(days=4):
        print('WARNING: First/last market dates are far from requested bounds; check completeness.',flush=True)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    # Year-by-year resets deliberately do NOT inherit earlier holdings.
    # Separate continuous trial tracks what happens if capital is never reset.
    periods=[(str(year),np.flatnonzero((dates.year==year) & (dates>=cal[0]) & (dates<=cal[-1])))
             for year in range(2015,2027)]
    periods=[(y,ids) for y,ids in periods if len(ids)>0]
    periods.append(('continuous_2015_2026',np.flatnonzero((dates>=cal[0])&(dates<=cal[-1]))))
    all_trials=[]; sample_equity=[];sample_trades=[];sample_holdings=[]
    for label,indices in periods:
        bench,btype=spy_period_return(spy,dates[indices[0]],dates[indices[-1]])
        for k in range(a.seeds):
            seed=a.seed+k
            # Each seed's yearly run restarts a fresh independent RNG at Jan 1.
            summary,equity,trades,open_rows=simulate(indices,dates,symbols,op,hi,cl,valid,
                capital=a.capital,buy_limit=a.buy_limit,target=a.target,seed=seed,period=label,
                keep_details=(k==0))
            summary['benchmark_pct']=bench
            summary['benchmark_type']=btype
            all_trials.append(summary)
            if k==0:
                sample_equity.extend(equity)
                sample_trades.extend(trades)
                sample_holdings.extend(open_rows)
        sub=pd.DataFrame(all_trials[-a.seeds:])
        print(f'{label:21s} n={a.seeds:4d} mean ${sub.total_profit.mean():>9,.2f} '
              f'median ${sub.total_profit.median():>9,.2f} profit {(sub.total_profit>0).mean()*100:5.1f}% '
              f'SPY {bench if np.isfinite(bench) else "N/A"}%',flush=True)
    trials=pd.DataFrame(all_trials)
    summary=aggregate(trials)
    # Save the distribution of ALL seeds, plus detailed audit data for seed0.
    trials.to_csv(out/'trials_by_seed.csv',index=False)
    summary.to_csv(out/'summary_by_year.csv',index=False)
    pd.DataFrame(sample_equity).to_csv(out/'equity_first_seed.csv',index=False)
    pd.DataFrame(sample_trades,columns=TRADE_FIELDS).to_csv(out/'trades_first_seed.csv',index=False)
    pd.DataFrame(sample_holdings).to_csv(out/'open_positions_first_seed.csv',index=False)
    with open(out/'settings.json','w') as f:
        json.dump({'data':str(a.data),'range':[a.start,a.end],'capital':a.capital,
                   'buy_limit':a.buy_limit,'target':a.target,'seeds':a.seeds,'seed0':a.seed,
                   'rules':'random prior-session; OPEN buy; +5% HIGH limit; hold losers; settled cash',
                   'known_limitations':['CURRENT S&P 500 membership survivorship bias',
                     'delisted stocks missing; potential stale-position valuation bias',
                     'no dividends in stock strategy, no slippage, commissions or taxes',
                     'SPY benchmark adjusted total return only if adj_close present']},f,indent=2)
    print('\nSaved:',out.resolve(),flush=True)
    print(summary[['period','number_simulations','mean_profit','median_profit','profitable_pct',
                   'spy_return_pct','beat_spy_pct']].to_string(index=False),flush=True)
    print('\nCAUTION: Current-constituent S&P 500 data contains survivorship bias; this is NOT proof of a tradable edge.',flush=True)

if __name__=='__main__':
    main()
