#!/usr/bin/env python3
# Copyright (c) 2026 Andrei Akimov.
# SPDX-License-Identifier: MIT
# Licensed under the MIT License; see LICENSE for details.
# Developed by Andrei Akimov with assistance from OpenAI ChatGPT.

"""Download today's S&P 500 constituents' 2014-12..2026-10 OHLC + SPY.

WARNING: This is a CURRENT-CONSTITUENT list, not historical index membership.
Research based on it is subject to survivorship bias.

Install: python3 -m pip install yfinance pandas requests lxml
Run:     python3 download_sp500_2015_2026.py

Writes one resumable gzip CSV per batch plus a consolidated CSV.GZ.
"""
import argparse
from io import StringIO
from pathlib import Path
import sys
import time

import pandas as pd


def current_tickers():
    """Fetch the CURRENT S&P 500 symbol list (not historical membership).

    This is a convenience, not a point-in-time backtest universe.
    Removed/bankrupt stocks are underrepresented, creating survivorship bias.
    """
    import requests
    pages = [
        ('wikipedia', 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'),
        ('github', 'https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv'),
    ]
    for name, url in pages:
        try:
            resp=requests.get(url,timeout=45,headers={'User-Agent':'Mozilla/5.0 (research backtest)'})
            resp.raise_for_status()
            if name=='wikipedia':
                tables=pd.read_html(StringIO(resp.text))
                table=next(t for t in tables if 'Symbol' in t.columns)
            else:
                table=pd.read_csv(StringIO(resp.text))
            symbols=sorted(set(table['Symbol'].astype(str).str.strip().str.replace('.','-',regex=False)))
            if len(symbols)<400:
                raise ValueError(f'Unusually few symbols: {len(symbols)}')
            print(f'Found {len(symbols)} CURRENT S&P 500 ticker symbols via {name}',flush=True)
            return sorted(set(symbols)|{'SPY'})
        except Exception as e:
            print(f'Failed to fetch universe from {name}: {e}',file=sys.stderr,flush=True)
    raise RuntimeError('Could not download CURRENT S&P 500 members. Supply --tickers-file containing ticker symbols.')


def read_tickers(path):
    """Read a user-provided symbol CSV as an alternative selection universe."""
    df=pd.read_csv(path)
    for c in ['symbol','Symbol','ticker','Ticker']:
        if c in df.columns:
            return sorted(set(df[c].astype(str).str.strip().str.replace('.','-',regex=False))|{'SPY'})
    if len(df.columns)==1:
        return sorted(set(df.iloc[:,0].astype(str).str.strip().str.replace('.','-',regex=False))|{'SPY'})
    raise ValueError('Tickers CSV must contain symbol or ticker column')


def one_batch(symbols, start, end):
    """Download raw OHLC and adjusted close in long date/symbol format.

    yahoo/yfinance end dates are EXCLUSIVE. Raw OHLC is used for trades;
    optional adjusted close is used by the backtest only for SPY.
    """
    import yfinance as yf
    data=yf.download(tickers=symbols,start=start,end=end,interval='1d',group_by='ticker',
         auto_adjust=False,actions=False,threads=8,progress=False,multi_level_index=True,timeout=30)
    if data is None or data.empty:
        return pd.DataFrame()
    pieces=[]
    # yfinance may deliver different MultiIndex column orders depending
    # on version/number of tickers; handle both without guessing fields.
    for symbol in symbols:
        frame=None
        if isinstance(data.columns,pd.MultiIndex):
            if symbol in data.columns.get_level_values(0):
                frame=data[symbol]
            elif symbol in data.columns.get_level_values(1):
                frame=data.xs(symbol,axis=1,level=1)
        elif len(symbols)==1:
            frame=data
        if frame is None or len(frame)==0:
            continue
        cols={str(c).lower().replace(' ','_'):c for c in frame.columns}
        if not all(x in cols for x in ['open','high','close']):
            continue
        used=['open','high','close']+(['adj_close'] if 'adj_close' in cols else [])
        tmp=pd.DataFrame({c:pd.to_numeric(frame[cols[c]],errors='coerce') for c in used})
        tmp['date']=pd.to_datetime(frame.index).tz_localize(None).date
        tmp['symbol']=symbol
        tmp=tmp.dropna(subset=['open','high','close'])
        tmp=tmp[tmp.open.gt(0)&tmp.close.gt(0)&tmp.high.ge(tmp.open)&tmp.high.ge(tmp.close)]
        if not tmp.empty:
            pieces.append(tmp.reset_index(drop=True)[['date','symbol']+used])
    return pd.concat(pieces,ignore_index=True) if pieces else pd.DataFrame()


def main():
    """Download batches, resume cached batches, and consolidate data."""
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--start',default='2014-12-01',help='Download includes prior trading date for Jan 2015')
    p.add_argument('--end',default='2026-10-24',help='EXCLUSIVE YYYY-MM-DD; last test date Oct 23')
    p.add_argument('--tickers-file',help='Optional CSV of symbols (or provide default current S&P 500)')
    p.add_argument('--batch-size',type=int,default=20)
    p.add_argument('--out',default='downloaded_prices_2015_2026.csv.gz')
    p.add_argument('--cache',default='sp500_historical_cache')
    p.add_argument('--pause',type=float,default=1.0)
    p.add_argument('--force',action='store_true',help='Re-download already cached batches')
    a=p.parse_args()
    symbols=read_tickers(a.tickers_file) if a.tickers_file else current_tickers()
    if a.batch_size<1:
        p.error('--batch-size must be positive')
    cache=Path(a.cache);cache.mkdir(parents=True,exist_ok=True)
    groups=[symbols[i:i+a.batch_size] for i in range(0,len(symbols),a.batch_size)]
    successes=0
    for i,group in enumerate(groups):
        # Checkpoints reduce repeated network traffic and allow retries.
        # Use --force if you need to re-fetch all batches.
        filepath=cache/f'batch_{i:03d}.csv.gz'
        if filepath.exists() and not a.force:
            print(f'[{i+1}/{len(groups)}] cached {filepath.name}',flush=True)
            successes+=1
            continue
        print(f'[{i+1}/{len(groups)}] fetching {group[0]}..{group[-1]} ({len(group)} symbols)',flush=True)
        got=pd.DataFrame()
        for attempt in range(3):
            try:
                got=one_batch(group,a.start,a.end)
                if not got.empty:
                    break
                raise RuntimeError('Batch returned zero daily bars')
            except Exception as exc:
                print(f'  attempt {attempt+1}/3: {exc}',file=sys.stderr,flush=True)
                time.sleep(3*(attempt+1))
        if got.empty:
            print('  FAILED: this batch was not saved; rerun to retry',file=sys.stderr,flush=True)
            continue
        got.to_csv(filepath,index=False,compression='gzip')
        successes+=1
        print(f'  saved {len(got):,} records from {got.symbol.nunique()} symbols',flush=True)
        if a.pause>0:
            time.sleep(a.pause)
    if successes<len(groups):
        print('WARNING: some batches failed. Rerun before interpreting results.',file=sys.stderr,flush=True)
    files=[cache/f'batch_{i:03d}.csv.gz' for i in range(len(groups)) if (cache/f'batch_{i:03d}.csv.gz').exists()]
    if not files:
        raise RuntimeError('No price batches available')
    combined=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
    # Keep only one bar per ticker and date. Cached data may still have
    # missing quotes; duplicate removal does not fill those gaps.
    combined=combined.drop_duplicates(['date','symbol']).sort_values(['date','symbol'])
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    combined.to_csv(out,index=False,compression='gzip' if str(out).endswith('.gz') else None)
    print(f'Combined {len(combined):,} rows, {combined.symbol.nunique()} tickers, '
          f'{combined.date.min()}..{combined.date.max()} -> {out}',flush=True)
    print('CAUTION: ticker list is current members, NOT actual historic S&P 500 membership.',flush=True)

if __name__=='__main__':
    main()
