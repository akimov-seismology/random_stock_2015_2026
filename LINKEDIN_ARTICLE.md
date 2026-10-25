# Can Random Stock Picking Be Profitable? A Test Using 11 Years of Stock Market Data

I recently became interested in stock-trading strategies. I am not an experienced trader, but I am curious about how different strategies work.

Recently, while searching Google, I came across a claim that most individual stock traders lose money.

I don't remember what I was searching for, but this caught my attention.

Similar claims are common on Reddit. For example, there is a discussion called ["90% of traders fail"](https://www.reddit.com/r/Daytrading/comments/1iti9mf/).

At the same time, we all know that many people make money in the stock market, and some become very rich.

Of course, long-term investing and active trading are not the same thing. But the difference between these success stories and the high percentage of unsuccessful traders made me curious.

**Why do so many people lose money while others make substantial profits? Is successful trading really so difficult? And what would happen if I simply selected stocks randomly?**

With my background in applied mathematics and scientific programming, I decided to investigate these questions using Python and historical stock prices.

## How the experiment works

The trading rules are very simple:

1. Randomly select stocks from the S&P 500.
2. Start with $50,000.
3. Buy up to $1,000 of each selected stock.
4. Sell a stock when its price increases by 5%.
5. If the price does not increase enough, keep the stock.
6. Use available settled cash to buy more randomly selected stocks.

There is no attempt to predict stock prices. I don't use company financial reports, technical indicators, or machine learning.

I simply choose stocks randomly and follow the same trading rules.

## From two years to twelve years

I started by testing the strategy on historical stock prices from **2025 and 2026**.

The results looked promising. Even with random stock selection, the simulations showed profits.

But perhaps those years were simply good for the stock market?

I decided to extend the experiment to cover **January 2015 through October 23, 2026**.

I ran 1,000 simulations, each using a different random selection of stocks.

The program also counts losses on stocks that have not been sold. This is important because selling only profitable stocks can make a strategy look successful even when the total portfolio is losing money.

## The results surprised me

Here are the average results from the 1,000 simulations covering the full period:

| Measurement | Result |
|---|---:|
| Starting money | $50,000 |
| Final portfolio value | $105,539 |
| Total profit | +$55,539 |
| Total return | +111.1% |
| Profit from completed trades | +$66,240 |
| Losses on unsold stocks | −$10,702 |
| Simulations that made money | 1,000 out of 1,000 |

**All 1,000 simulations ended with a profit.**

The total profit ranged from approximately $41,510 to $75,420.

I found this surprising because the program didn't try to select good companies. It simply selected stocks randomly.

However, there is another important result.

If I had invested the same $50,000 in SPY, an exchange-traded fund (ETF) that tracks the S&P 500 stock market index, and held it throughout the same period, the return would have been approximately 349%.

That is much better than the 111% average return from my random trading strategy.

So random stock selection made money in the simulation, but buying and holding the S&P 500 made considerably more.

## What happened in 2018 and 2022?

I also tested each year separately, starting each test with a new $50,000 portfolio.

Two years were especially interesting.

| Year | Random trading | SPY |
|---|---:|---:|
| 2018 | −3.5% | −5.2% |
| 2022 | −11.5% | −18.6% |

![Annual return comparison of random stock selection versus SPY, 2015–2026](linkedin_random_vs_spy_2015_2026_updated.png)

Both years were difficult for the stock market.

In 2018, Donald Trump was president. In 2022, Joe Biden was president. In both years, the Federal Reserve increased interest rates, although the economic conditions were different.

My random trading strategy lost money in both years, but **it lost less than SPY**.

In 2018, only 7% of the simulations ended with a profit. In 2022, none of them made money.

Why did the strategy lose less?

Perhaps because it sometimes kept part of the money in cash instead of stocks. Or perhaps the 5% selling rule helped.

I don't know yet.

## Why does random stock selection make money?

I can think of several possible reasons.

**1. The stock market generally goes up over time.**

Over the years covered by this experiment, the U.S. stock market grew considerably. Even randomly selected stocks had a good chance of increasing in value.

**2. The program sells stocks after a 5% increase.**

It repeatedly collects relatively small profits and uses the money to buy other stocks.

But there is a disadvantage. If a stock continues rising another 20% or 50%, the program misses those additional gains.

**3. Losing stocks are not sold immediately.**

Some stocks recover after falling and eventually reach the 5% profit target.

But others may remain below their purchase price for years.

For example, during the 2020 tests, the average maximum drop in portfolio value from an earlier peak was approximately 36%.

**4. Some money stays in cash.**

The program does not necessarily invest all $50,000 at the same time.

Holding cash may reduce losses when the market falls. But it also means missing some gains when the market rises.

I suspect this is one reason the strategy performed better than SPY in 2018 and 2022, but worse over the full period.

## Limitations

This is a computer experiment using historical stock prices, not a proven trading strategy.

**Survivorship bias:** The dataset contains current S&P 500 companies rather than the companies that belonged to the index at each historical date. Therefore, research based on this dataset is subject to survivorship bias. Companies that were removed from the index or delisted may be missing, which could overstate historical returns.

The simulation also uses simplified buying and selling rules. It does not include trading costs, price differences during execution, or taxes.

Dividends are included in the adjusted SPY comparison but not in the individual-stock trading results.

These details are important when interpreting the results.

## I would like to hear your opinion

I am approaching stock trading as a research problem. I enjoy working with historical data, testing ideas, and trying to understand unexpected results.

I would especially like to hear from experienced traders and people who work with financial data.

**Why do you think all 1,000 random simulations ended with a profit?**

Is there something important I am missing?

Do these results agree with your own trading experience?

I would appreciate your comments, including criticism. I am interested in understanding why the strategy works in the simulation and where it might fail.

#MonteCarlo #StockTrading #Python #Backtesting #QuantitativeResearch
