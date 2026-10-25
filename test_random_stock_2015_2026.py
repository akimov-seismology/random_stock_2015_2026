#!/usr/bin/env python3
# Copyright (c) 2026 Andrei Akimov.
# SPDX-License-Identifier: MIT
# Licensed under the MIT License; see LICENSE for details.
# Developed by Andrei Akimov with assistance from OpenAI ChatGPT.

"""Offline synthetic accounting and date-handling tests (no market claims)."""
from pathlib import Path
import tempfile
import numpy as np
import pandas as pd
from random_stock_2015_2026 import (simulate,build_panel,lag_for_day,read_prices,aggregate)


def test_settlement():
    """Test regulatory T+3 / T+2 / T+1 settlement boundary dates."""
    assert lag_for_day(pd.Timestamp('2015-01-05'))==3
    assert lag_for_day(pd.Timestamp('2017-09-04'))==3
    assert lag_for_day(pd.Timestamp('2017-09-05'))==2
    assert lag_for_day(pd.Timestamp('2024-05-27'))==2
    assert lag_for_day(pd.Timestamp('2024-05-28'))==1


def test_zero_cash_leverage_and_marks():
    """Verify simulated equity reconciliation and no borrowing.

    All quotes below are deliberately synthetic; this is NOT market data.
    One symbol reaches target and the other suffers an open loss.
    """
    days=pd.to_datetime(['2014-12-31','2015-01-02','2015-01-05','2015-01-06','2015-01-07','2015-01-08'])
    prices=[]
    for idx,day in enumerate(days):
        for s in ['A','B','SPY']:
            op = 100.0 if s!='SPY' else 200.0
            hi = 110.0 if (s=='A' and idx>=1) else op
            cl = 90.0 if (s=='B' and idx>=1) else op
            if s=='A' and idx>=1:
                cl=106.0
            prices.append(dict(date=day.date(),symbol=s,open=op,high=max(hi,op,cl),close=cl,adj_close=cl))
    d=pd.DataFrame(prices)
    d['date']=pd.to_datetime(d['date'])
    dates,cal,symbols,op,hi,cl,valid,spy=build_panel(d,'2015-01-01','2015-01-08')
    idx=np.flatnonzero((dates>=cal[0])&(dates<=cal[-1]))
    # Many fixed random seeds help catch seed-dependent bookkeeping errors.
    for seed in range(10):
        s,eq,tr,h=simulate(idx,dates,symbols,op,hi,cl,valid,capital=2000,buy_limit=1000,target=.05,
            seed=seed,period='2015',keep_details=True)
        assert len(eq)==len(cal)
        assert eq[-1]['equity'] >=0
        assert max(x['positions'] for x in eq)<=2
        assert abs(s['total_profit']-(s['realized_profit']+s['unrealized_profit']))<=.03
        assert all(x['cash']>=-0.01 for x in eq)
        assert all(x['unsettled']>=-0.01 for x in eq)
        assert all(x['profit']>=0 for x in tr)
        assert s['return_pct']>=-50 and s['return_pct']<=50


def test_yearly_reset():
    """Check that separate yearly simulations start with fresh capital."""
    dates=pd.to_datetime(['2014-12-31','2015-01-02','2015-01-05','2021-12-31','2022-01-03','2022-01-04','2026-10-22','2026-10-23'])
    records=[]
    for i,dt in enumerate(dates):
        for sym in ['XYZ','SPY']:
            prices=150 if sym=='SPY' else 100
            records.append({'date':dt,'symbol':sym,'open':prices,'high':prices*1.1,
                            'close':prices,'adj_close':prices})
    d=pd.DataFrame(records)
    d['date']=pd.to_datetime(d['date'])
    dates,cal,symbols,op,hi,cl,valid,spy=build_panel(d,'2015-01-01','2026-10-23')
    for y in (2015,2022,2026):
        idx=np.flatnonzero((dates.year==y)&(dates>=cal[0])&(dates<=cal[-1]))
        summ, eq, trades, _ = simulate(idx,dates,symbols,op,hi,cl,valid,
            capital=50000,buy_limit=1000,target=.05,seed=42,period=str(y),keep_details=True)
        assert summ['starting_capital']==50000
        assert summ['total_profit']>=0
        assert eq[-1]['equity']==summ['equity']


if __name__=='__main__':
    test_settlement(); test_zero_cash_leverage_and_marks(); test_yearly_reset()
    print('ALL OFFLINE TESTS PASSED')
