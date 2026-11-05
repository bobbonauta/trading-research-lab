# Experiment register

Last updated: 2026-11-05

This is the single canonical experiment register for Trading Research Lab. No other experiments or strategy variants are recorded.

## EXP-001 - Daily long-only SMA crossover

- **State:** CONCLUSA; the historical economic result is INCONCLUSIVE because the final test contains fewer than the frozen low-sample floor.
- **Hypothesis:** daily BTC trends may persist long enough for an SMA(20)/SMA(100) crossover to outperform cash after modeled costs; any effect may be absent or regime-dependent.
- **Rule frozen before observing returns:** enter long when SMA(20) crosses above SMA(100), exit when SMA(20) crosses below SMA(100); calculate the signal on a completed daily close and attempt execution at the next daily open. One cash-only position, no leverage, no short, no extra stop. The first 100 bars are warm-up. Keep indicator history, cash, and position continuous across the full 2018-2025 series. Attempt liquidation at the final close subject to the same order rules; if the terminal sale is rejected, retain and mark the position.
- **Sizing:** initial capital 10,000 USDT simulated; buy the greatest affordable quantity after modeled price impact and commission, rounded down to the frozen BTC quantity increment; leave residual USDT in cash. Assume full fills for accepted orders. Record orders rejected by the frozen quantity/notional rules. No interest on cash.
- **Instrument and period:** BTCUSDT Spot, Binance Vision monthly 1d klines, UTC, 2018-01-01 through 2025-12-31. The prior SPY/Alpaca candidate was superseded before any market return was observed; its history remains below.
- **Data provenance:** 96 monthly ZIPs and official CHECKSUM sidecars downloaded 2026-11-05 to local ignored path E:\EA Tester\data\binance\spot\monthly\klines\BTCUSDT\1d. All ZIP SHA-256 values matched both the Binance sidecars and the local manifest. Frozen dataset identity is each archive hash in download_manifest.json; Binance does not publish a separate immutable dataset version. Total compressed ZIP size is 208,117 bytes. The raw archives, sidecars, manifest, filter snapshot, and results are local and will not be committed.
- **Data quality:** all 2,922 UTC daily sessions are present once from 2018-01-01 through 2025-12-31, with zero missing dates and zero duplicates. All ZIP CRCs passed and each archive contains the expected single CSV. Each row has 12 columns; daily opens are midnight UTC and close timestamps span exactly one UTC day. OHLC values are finite, positive, and internally consistent; volume and trade-count fields are non-negative. Binance's Spot timestamps use milliseconds through 2024 and microseconds from 2025-01-01; this was confirmed in all rows (2,557 ms, 365 us). These checks do not independently compare prices with another feed. Binance provides the data as-is and disclaims accuracy and completeness.
- **Data terms:** Binance Vision Dataset Terms v1.0 dated 2026-08-26 permit personal non-production historical backtesting and non-commercial research. Any publicly redistributed derived result must include Binance Vision attribution and remain under CC BY-NC-SA 4.0. This scope applies only to material derived from this dataset and does not choose a project-wide software license. Raw data remains private/local. No commercial use, live signals, or trading is authorized. References: [Binance Public Data format, timestamps, checksums, and archive updates](https://github.com/binance/binance-public-data/blob/master/README.md), [Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).
- **UTC and kline rules:** Binance Spot API identifies klines by open time and defaults timeZone to UTC; Binance's public data README identifies the archives as sourced from /api/v3/klines. Reference: [Binance Spot API kline documentation](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#klinecandlestick-data).
- **Quantity/notional constraints frozen:** public exchangeInfo?symbol=BTCUSDT snapshot saved locally at 2026-11-05T08:29:29.9063864Z; status TRADING. LOT_SIZE: min 0.00001000 BTC, step 0.00001000, max 9,000 BTC. MARKET_LOT_SIZE: min 0, step 0, max 125.26150288 BTC. NOTIONAL: min 5 USDT applies to market orders; max 9,000,000 USDT does not apply to market orders. The model uses min and increment 0.00001 BTC, max 125.26150288 BTC, min notional 5 USDT; min notional uses next-open/terminal reference price as a daily-bar proxy. Because market step is zero, nonzero LOT_SIZE step is used as a conservative increment. These are current observed rules, not historical filter records; historical rule changes were not independently verified. Reference: [Binance Spot symbol filters](https://github.com/binance/binance-spot-api-docs/blob/master/filters.md).
- **Fixed windows:** development 2018-2021 (1,461 days); validation 2022-2023 (730 days); final test 2024-2025 (731 days). No reset or retuning at boundaries. Also report the full 2018-2025 period as context.
- **Costs frozen before the market run:** commission 10 bps per fill, full spread 2 bps (1 bp per side), slippage 3 bps per side. Stress doubles each input to 20 / 4 / 6 bps. These are assumptions, not historical Binance fees or measured execution costs. Base and stress use identical data, rules, capital, and benchmark.
- **Benchmark:** independently computed BTCUSDT buy-and-hold, entered at the first daily open (2018-01-01), held through the continuous period and liquidated at the final close if filters permit. Same 10,000 USDT, cost scenarios, and order constraints. SPY is not a benchmark for this experiment.
- **Metric definitions:** window return is marked equity from the preceding daily close (or initial capital for the first date) to the last daily close. Maximum drawdown uses daily close equity plus the starting value. Exposure is the percentage of daily close observations with BTC held. Completed trades are assigned to the window containing their exit; expectancy and profit factor use net trade P&L. Costs are assigned to the window containing each fill and include price impact plus commission. Profit factor is null if there are no losing trades. Apply the same calculations to the benchmark.
- **Low-sample criterion frozen before the market run:** fewer than 30 completed strategy trades exiting in the 2024-2025 final test means the economic result is **INCONCLUSIVE**. Thirty is an operational low-sample floor, not a power calculation; meeting it alone does not establish a trading edge. Do not change parameters or windows if the count is low. This order defines no profitability promotion threshold.
- **Research count:** one fixed rule and one instrument chosen for public data access before returns were viewed; zero tuned variants and zero prior economic runs.
- **Technical checks:** Python 3.11.5; python -B -m unittest -v test_backtest passed 21/21 synthetic checks. Coverage includes 12-column ingest, both timestamp units, UTC candle boundaries, checksum/ZIP integrity, missing dates, signal/fill timing, fractional sizing, min/max quantity and notional, costs, accounting reconciliation, independent benchmark, reproducibility, and window metrics. The actual loader revalidated all 96 archives and 2,922 rows before the economic run.
### Economic evaluation (one historical backtest; not paper trading)

The economic run used the frozen base costs and one doubled-cost sensitivity. It used the same data, capital, strategy rules, and independent buy-and-hold benchmark in both cases. Results below are historical backtest output, not account activity or paper trading. Percentages are not annualized; monetary values are USDT.

**Strategy by window**

| Cost case | Window | Net return | Max DD | Trades | PF | Expectancy | Win rate | Exposure | Costs |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Base | Development | 371.51% | 60.14% | 6 | 4.49 | 6,191.90 | 50.00% | 52.91% | 331.51 |
| Base | Validation | 34.03% | 23.73% | 3 | 0.81 | -915.72 | 33.33% | 39.86% | 448.64 |
| Base | Final test | 76.37% | 40.52% | 6 | 2.84 | 11,176.02 | 50.00% | 66.21% | 1,498.53 |
| Base | Full period | 1,014.60% | 60.14% | 15 | 2.65 | 6,764.02 | 46.67% | 52.98% | 2,278.69 |
| Doubled | Development | 363.66% | 60.36% | 6 | 4.41 | 6,060.97 | 50.00% | 52.91% | 655.49 |
| Doubled | Validation | 32.72% | 23.95% | 3 | 0.78 | -1,022.21 | 33.33% | 39.86% | 877.93 |
| Doubled | Final test | 73.68% | 41.02% | 6 | 2.76 | 10,596.09 | 50.00% | 66.21% | 2,894.93 |
| Doubled | Full period | 968.76% | 60.36% | 15 | 2.59 | 6,458.38 | 46.67% | 52.98% | 4,428.35 |

**Buy-and-hold benchmark**

| Cost case | Window | Net return | Max DD | Costs (USDT) |
|---|---|---:|---:|---:|
| Base | Development | 236.49% | 81.18% | 13.98 |
| Base | Validation | -8.51% | 66.93% | 0.00 |
| Base | Final test | 107.00% | 32.02% | 89.31 |
| Base | Full period | 537.25% | 81.18% | 103.30 |
| Doubled | Development | 236.02% | 81.18% | 27.94 |
| Doubled | Validation | -8.51% | 66.93% | 0.00 |
| Doubled | Final test | 106.71% | 32.02% | 178.33 |
| Doubled | Full period | 535.46% | 81.18% | 206.26 |

**Interpretation:** the final test has 6 completed trades, below the precommitted floor of 30, so its result is INCONCLUSIVE and neither validates nor rejects the hypothesis. It underperforms buy-and-hold on final-test return in both cases (76.37% vs 107.00%; 73.68% vs 106.71%) and has higher final-test drawdown (40.52% vs 32.02%; 41.02% vs 32.02%). Validation PF is below 1 and expectancy is negative in both scenarios. Full-period returns are descriptive backtest values only; they do not establish a repeatable edge.

**Local reproducibility files:** deterministic engine SHA-256 18D844315C00FBE6B753B389C011DD6ECF48B5F4CF6B60CD0C68C888094B2C7E. Local JSON result data/binance/spot/monthly/klines/BTCUSDT/1d/EXP-001-results.json SHA-256 21F2DDFF57A9CC466BE953D627A342A154B8C2386A3F4D6D1E221CB5DE14223A. Dataset manifest SHA-256 C45929FBC677940F35A2C3E8882C00FECEB4E7B53357B2605BDA8C6061EE06E0. Raw data and JSON remain local and ignored by Git.

**Attribution and license:** these published derived metrics are attributed to Binance Vision and scoped under CC BY-NC-SA 4.0 as required by the dataset terms. This does not choose a license for the whole repository.
- **History:** an earlier EXP-001 draft proposed SPY/Alpaca. The 2026-11-05 review found no authenticated data access, so that candidate was blocked. No SPY data or returns were obtained. BTCUSDT replaced it before strategy returns were examined; SMA20/SMA100 did not change.
- **Limitations:** daily-bar execution with fixed bps impact assumes full fills and cannot measure historical bid/ask, liquidity, latency, partial fills, outages, or past exchange filter rules. There is no independent second-feed comparison. Stress costs are a sensitivity check, not proof of execution robustness. Backtest results do not authorize paper or real trading.
- **Reproduction:** do not rerun except under a new order. The command is python -B backtest.py --dataset-dir data/binance/spot/monthly/klines/BTCUSDT/1d --output data/binance/spot/monthly/klines/BTCUSDT/1d/EXP-001-results.json. The output JSON is local and ignored. Commit only reviewed source and registry documentation; never stage raw ZIPs, sidecars, or local results.
- **Decision:** stop after EXP-001. No paper trading, new strategies, parameter search, account access, or order execution.
