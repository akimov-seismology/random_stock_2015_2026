#!/usr/bin/env python3
# Copyright (c) 2026 Andrei Akimov.
# SPDX-License-Identifier: MIT
# Licensed under the MIT License; see LICENSE for details.
# Developed by Andrei Akimov with assistance from OpenAI ChatGPT.

"""Create two PNG charts from completed backtest results.
python3 plot_random_2015_2026.py --results random_2015_2026_results
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def main():
    """Load completed backtest CSVs and save two static PNG summaries."""
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',default='random_2015_2026_results')
    a=p.parse_args()
    folder=Path(a.results)
    agg=pd.read_csv(folder/'summary_by_year.csv')
    trials=pd.read_csv(folder/'trials_by_seed.csv')
    # Exclude the continuous account: these charts compare independent
    # calendar-year starts, each funded with the same $50,000.
    agg=agg[agg.period.str.fullmatch(r'20\d\d')].sort_values('period')
    years=agg.period.to_numpy()
    x=np.arange(len(years))
    fig, ax=plt.subplots(figsize=(11,5.5))
    # Mean and median show distribution asymmetry across random seeds.
    ax.plot(x,agg.mean_return_pct,label='Monte Carlo mean return',marker='o')
    ax.plot(x,agg.median_return_pct,label='Monte Carlo median return',marker='s')
    if agg.spy_return_pct.notna().any():
        ax.plot(x,agg.spy_return_pct,label='SPY buy-and-hold return',marker='^')
    ax.axhline(0,linewidth=1,color='gray')
    ax.set_xticks(x,years)
    ax.set_ylabel('Annual return (%)')
    ax.set_title('Can Random Stock Picking Be Profitable?\nA Test Using 11 Years of Stock Market Data')
    ax.legend()
    fig.tight_layout()
    fig.savefig(folder/'annual_return_vs_SPY.png',dpi=180)
    plt.close(fig)

    df=trials[trials.period.str.fullmatch(r'20\d\d')].copy()
    # Boxplots summarize the whole seed distribution, not only the
    # sample portfolio for seed0 or a handpicked profitable run.
    data=[df.loc[df.period==year,'total_profit'].to_numpy() for year in years]
    fig, ax=plt.subplots(figsize=(11,5.5))
    ax.boxplot(data,tick_labels=years,showfliers=False)
    ax.axhline(0,color='gray',linewidth=1)
    ax.set_title('Can Random Stock Picking Be Profitable? | Profit Distribution by Year')
    ax.set_ylabel('Total profit or loss ($)')
    fig.tight_layout()
    fig.savefig(folder/'annual_profit_distribution.png',dpi=180)
    plt.close(fig)
    print('Created',folder/'annual_return_vs_SPY.png')
    print('Created',folder/'annual_profit_distribution.png')

if __name__=='__main__':
    main()
