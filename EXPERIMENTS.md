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

## TRL-003 frozen protocol (registered before new economic runs)

- **Frozen on:** 2026-11-05, before running any EXP-002/003/004 market evaluation.
- **Scope:** exactly three hypotheses and nine parameter configurations. Every configuration is evaluated on development only. For each hypothesis, select one configuration by the mechanical rule below and evaluate only that selected configuration on validation. A base/stress cost pair is a sensitivity scenario for the same parameter configuration, not an additional configuration. No genetic, neural, broad, adaptive, or post-validation search.
- **Instrument/data:** BTCUSDT Spot, Binance Vision daily UTC klines already stored under the EXP-001 ignored local dataset path. Load only 2018-01-01 through 2023-12-31 (72 monthly archives). Do not load or inspect 2024-2025 for these experiments. The 2024-2025 period is already observed in EXP-001 and is not a blind final test for this research. No new data is downloaded or published.
- **Windows and isolation:** development 2018-01-01 through 2021-12-31 (1,461 daily bars); validation 2022-01-01 through 2023-12-31 (730 daily bars). Each window is a separate simulation with 10,000 USDT starting cash, no position carried across its boundary, and terminal close liquidation subject to the same quantity rules. Validation indicators may use only the preceding 2018-2021 bars as causal warm-up; no pre-validation position or equity is carried. Signals are formed at a completed daily close and execute at the next daily open. Full-bar OHLC data are not available to a policy beyond the signal date.
- **Sizing/risk shared by all candidates:** one long-only BTC position at a time; use available cash, no shorting, leverage, pyramiding, or interest; use the existing quantity step, maximum quantity and minimum-notional snapshot from EXP-001. The snapshot records current observed rules only, not historical filter history. Candidate-specific exits below are evaluated at the daily close and execute at the next open. A terminal position is liquidated at the window's final close if accepted. Full fills are assumed for accepted orders, as in EXP-001.
- **Costs/benchmark:** preserve EXP-001 assumptions: base commission 10 bps per fill, full spread 2 bps and slippage 3 bps per side; stress doubles each input to 20/4/6 bps. These are modeled assumptions, not historical paid fees or measured execution. Compare each window with independent BTCUSDT buy-and-hold started at that window's first daily open, using the same starting capital, cost scenario and quantity rules.
- **Metrics:** use existing engine definitions for net return (not annualized), maximum daily-close drawdown, completed trades assigned by exit date, net-trade profit factor and expectancy, win rate, daily-close exposure, and costs assigned by fill date. Report rejected orders, ending position and final equity as diagnostics. Run and record all three metrics sets for every development configuration (base and doubled costs) and for each selected validation configuration (base and doubled costs); also report corresponding buy-and-hold metrics.
- **Fitting and deterministic selection:** run every prelisted configuration on development. Select one per hypothesis by highest development net return under base costs; break exact ties by lower development maximum drawdown, then lexicographically lower configuration ID. The doubled-cost development result is reported but does not influence selection. Do not add or alter configurations after seeing any result. Record every attempted configuration, including negative and zero-trade results.
- **Predeclared validation gates:** a selected configuration is a **preliminary candidate** only if it has at least 30 completed trades in each validation cost scenario; base-cost validation profit factor > 1; positive base-cost validation net return; positive doubled-cost validation net return; and validation maximum drawdown below the corresponding buy-and-hold drawdown in both cost scenarios. The 30-trade floor is an operational minimum, not a power calculation. Fewer than 30 validation trades means **INCONCLUSIVE**. With at least 30 trades, failure of any other gate means **SCARTATA**. Passing all gates means **CANDIDATA preliminare only**, not evidence of future edge and not authorization for forward testing or paper trading. No criterion may be changed after results are observed.

### EXP-002 - Daily Donchian channel trend breakout

- **Hypothesis:** BTC directional flows may persist after a close breaks a prior multi-day price ceiling; a trailing channel exit may retain prolonged advances while limiting exposure to reversals.
- **Entry:** while flat, at close t enter if close[t] is strictly greater than the maximum high of the immediately preceding entry-lookback completed bars. Exclude bar t from the channel.
- **Exit/risk:** while long, at close t exit if close[t] is strictly below the minimum low of the immediately preceding exit-lookback completed bars. Exclude bar t from the channel. This trailing channel is the strategy exit; shared cash-only/no-leverage/no-pyramiding limits apply. No separate intraday stop or target.
- **Frozen configurations (entry bars / exit bars):** D20_10 = 20/10; D55_20 = 55/20; D100_40 = 100/40. Exactly three.
- **Expected failure:** choppy ranges can create repeated false breakouts and transaction costs; long bear markets can keep the strategy out or cause losses before the trailing exit.
- **Benchmark/exclusion:** window-specific BTCUSDT buy-and-hold. Apply the shared validation gates without exceptions.

### EXP-003 - Daily short-horizon RSI mean reversion

- **Hypothesis:** sharp short-term BTC selling may be temporarily overextended and partly reverse as liquidity/positioning normalizes; persistent downtrends are the central alternative explanation.
- **Indicator:** simple RSI over the most recent N close-to-close changes, using arithmetic mean gains and absolute losses; RSI is 50 when both means are zero and 100 when losses are zero but gains are positive. Only bars available through the signal close are used.
- **Entry:** while flat, at close t enter when RSI(N) is less than or equal to the configured oversold threshold.
- **Exit/risk:** while long, at close t exit when RSI(N) is greater than or equal to 50, or when the configured maximum number of daily bars since the entry fill has elapsed, whichever occurs first. Exits execute at the next open. Shared cash-only/no-leverage/no-pyramiding limits apply; there is no intraday protective stop, so overnight gap risk remains.
- **Frozen configurations (RSI period / entry threshold / exit threshold / maximum held bars):** R2_05 = 2/5/50/10; R2_10 = 2/10/50/10; R3_10 = 3/10/50/10. Exactly three.
- **Expected failure:** prolonged downtrends can keep RSI oversold, trigger repeated entries, or leave a position open until the time exit; rebound can occur before the next-open fill or fail to cover costs.
- **Benchmark/exclusion:** window-specific BTCUSDT buy-and-hold. Apply the shared validation gates without exceptions.

### EXP-004 - Daily positive volatility-shock continuation

- **Hypothesis:** an unusually large positive BTC daily move relative to recently realized range may reflect persistent information or order-flow rather than an immediate reversal; fixed holding periods test whether any continuation survives costs.
- **Volatility reference:** at close t, calculate arithmetic mean true range over the 14 completed bars before t; true range for each such bar uses its high, low and the preceding close. Normalize this mean by close[t-1]. Compare with the positive close-to-close return from t-1 to t. No current-bar high/low is included in the volatility reference.
- **Entry:** while flat, at close t enter if close[t]/close[t-1]-1 is greater than or equal to k times the prior 14-bar mean true range divided by close[t-1].
- **Exit/risk:** while long, exit at close t after the configured number of completed daily bars since the entry fill; execute at the next open. Shared cash-only/no-leverage/no-pyramiding limits apply. There is no intraday protective stop; gap risk remains.
- **Frozen configurations (shock multiple k / maximum held bars):** V1_3 = 1.0/3; V1_5 = 1.5/5; V2_10 = 2.0/10. Exactly three.
- **Expected failure:** positive shocks can be short-lived, driven by news that reverses, or concentrated in a few observations; sparse signals can leave too few validation trades, and next-open execution can surrender the measured close-to-close impulse.
- **Benchmark/exclusion:** window-specific BTCUSDT buy-and-hold. Apply the shared validation gates without exceptions.

**Implementation constraint frozen:** make only the minimal extension to the existing deterministic execution/accounting engine so a causal signal policy can emit BUY/SELL decisions. Keep fills, order timing, sizing, costs, constraints, metrics and buy-and-hold centralized; do not add another engine, registry, dependency or data source. Add synthetic checks for all policy rules, next-open execution, position/time-stop behavior, and the history cutoff before any economic evaluation.

## TRL-003 results (single bounded historical research cycle)

- **Execution:** 2026-11-05, after the frozen protocol above and 28/28 synthetic checks passed. Exactly nine parameter configurations were evaluated on development (18 base/stress runs); exactly one selected configuration per hypothesis was evaluated on validation (6 base/stress runs). Four window-matched buy-and-hold benchmark runs were calculated. No parameter was changed after validation was observed.
- **Initial project state:** branch `main`, starting HEAD `7b60a6ac08300be8a77b5773f7924f37e354a4db`; working tree was clean. The run used the existing Python 3.11.5 environment and the existing BTCUSDT Binance Vision dataset, without new downloads or dependencies.
- **Data used:** only the requested 72 monthly archives and 2,191 daily bars from 2018-01-01 through 2023-12-31. The existing loader rechecked every selected archive SHA-256 against the official sidecar and local manifest and validated ZIP/CSV, OHLC and daily calendar. Manifest SHA-256: `C45929FBC677940F35A2C3E8882C00FECEB4E7B53357B2605BDA8C6061EE06E0`. Files for 2024-2025 were not opened by this run and were not used for fitting, selection or promotion.
- **Capital/execution:** 10,000 USDT independently at each window start; current observed quantity constraints inherited from EXP-001; long-only, one cash-funded position, no leverage; signal at completed close, next-open execution; terminal close liquidation when accepted. No rejected orders or residual positions occurred in any recorded strategy run.
- **Interpretation note:** 2022-2023 validation is historical and is not a fully blind laboratory-wide holdout: EXP-001 had already published SMA results for that period. The new strategy rules and nine parameter configurations were frozen before their TRL-003 runs, but this validation cannot be described as an independent prospective test. 2024-2025 was not loaded or used.
- **Selection:** EXP-002 selected D20_10 (development base return +861.61%); EXP-003 selected R2_05 (-33.69%, the highest of its three development results, though all were negative); EXP-004 selected V2_10 (+103.25%). The pre-registered ranking and validation gates were applied unchanged.

### Development results: all nine configurations

Percentages are not annualized; P&L expectancy and costs are USDT. PF is net profit factor.
| Experiment | Config | Cost case | Net return % | Max DD % | Trades | PF | Expectancy USDT | Win % | Exposure % | Costs USDT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| EXP-002 | D20_10 | base | 861.61 | 37.66 | 15 | 2.83 | 5744.06 | 60.00 | 45.52 | 1723.07 |
| EXP-002 | D20_10 | stress_double_all_costs | 822.06 | 38.09 | 15 | 2.78 | 5480.39 | 60.00 | 45.52 | 3341.62 |
| EXP-002 | D55_20 | base | 514.95 | 38.80 | 7 | 12.52 | 7356.36 | 57.14 | 42.64 | 617.94 |
| EXP-002 | D55_20 | stress_double_all_costs | 503.01 | 39.14 | 7 | 11.76 | 7185.85 | 57.14 | 42.64 | 1219.57 |
| EXP-002 | D100_40 | base | 362.68 | 53.13 | 5 | 3.04 | 7253.65 | 40.00 | 42.64 | 471.93 |
| EXP-002 | D100_40 | stress_double_all_costs | 356.25 | 53.39 | 5 | 2.99 | 7125.03 | 40.00 | 42.64 | 935.62 |
| EXP-003 | R2_05 | base | -33.69 | 75.61 | 162 | 0.82 | -20.80 | 63.58 | 31.07 | 2316.78 |
| EXP-003 | R2_05 | stress_double_all_costs | -57.87 | 78.10 | 162 | 0.66 | -35.72 | 58.64 | 31.07 | 3718.71 |
| EXP-003 | R2_10 | base | -45.23 | 79.73 | 171 | 0.74 | -26.45 | 62.57 | 32.38 | 1916.74 |
| EXP-003 | R2_10 | stress_double_all_costs | -66.07 | 82.20 | 171 | 0.58 | -38.64 | 57.89 | 32.38 | 3029.54 |
| EXP-003 | R3_10 | base | -49.54 | 69.34 | 95 | 0.71 | -52.15 | 64.21 | 24.71 | 1327.74 |
| EXP-003 | R3_10 | stress_double_all_costs | -61.33 | 73.97 | 95 | 0.62 | -64.56 | 62.11 | 24.71 | 2354.13 |
| EXP-004 | V1_3 | base | 27.45 | 31.46 | 84 | 1.14 | 32.68 | 50.00 | 17.25 | 3028.09 |
| EXP-004 | V1_3 | stress_double_all_costs | 0.74 | 34.92 | 84 | 1.00 | 0.88 | 46.43 | 17.25 | 5368.04 |
| EXP-004 | V1_5 | base | 90.35 | 20.26 | 31 | 2.05 | 291.44 | 54.84 | 10.61 | 1097.79 |
| EXP-004 | V1_5 | stress_double_all_costs | 74.52 | 21.71 | 31 | 1.86 | 240.39 | 51.61 | 10.61 | 2091.80 |
| EXP-004 | V2_10 | base | 103.25 | 21.74 | 15 | 4.63 | 688.33 | 80.00 | 10.27 | 545.48 |
| EXP-004 | V2_10 | stress_double_all_costs | 94.89 | 21.96 | 15 | 4.27 | 632.60 | 73.33 | 10.27 | 1066.47 |

### Selected validation results

| Experiment | Selected config | Cost case | Net return % | Max DD % | Trades | PF | Expectancy USDT | Win % | Exposure % | Costs USDT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| EXP-002 | D20_10 | base | -0.78 | 39.19 | 11 | 0.98 | -7.09 | 36.36 | 42.74 | 245.86 |
| EXP-002 | D20_10 | stress_double_all_costs | -3.79 | 39.96 | 11 | 0.92 | -34.46 | 36.36 | 42.74 | 484.36 |
| EXP-003 | R2_05 | base | -61.50 | 69.69 | 92 | 0.42 | -66.85 | 58.70 | 36.85 | 1109.98 |
| EXP-003 | R2_05 | stress_double_all_costs | -70.24 | 74.09 | 92 | 0.34 | -76.35 | 46.74 | 36.85 | 1996.09 |
| EXP-004 | V2_10 | base | 30.17 | 19.56 | 7 | 2.00 | 431.07 | 42.86 | 9.59 | 201.63 |
| EXP-004 | V2_10 | stress_double_all_costs | 27.65 | 19.79 | 7 | 1.89 | 394.98 | 42.86 | 9.59 | 399.11 |

### Buy-and-hold benchmark

| Window | Cost case | Net return % | Max DD % | Trades | PF | Expectancy USDT | Win % | Exposure % | Costs USDT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| development | base | 236.02 | 81.18 | 1 | — | 23602.13 | 100.00 | 99.93 | 61.08 |
| development | stress_double_all_costs | 235.08 | 81.18 | 1 | — | 23508.09 | 100.00 | 99.93 | 121.97 |
| validation | base | -8.77 | 66.93 | 1 | 0.00 | -876.61 | 0.00 | 99.86 | 26.77 |
| validation | stress_double_all_costs | -9.02 | 66.93 | 1 | 0.00 | -902.13 | 0.00 | 99.86 | 53.47 |

### Frozen validation gates and classifications

| Experiment | Selected | Trades base/stress | Base PF | Return base/stress % | Max DD base/stress % | Benchmark DD base/stress % | Classification |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| EXP-002 | D20_10 | 11/11 | 0.98 | -0.78/-3.79 | 39.19/39.96 | 66.93/66.93 | INCONCLUSIVE |
| EXP-003 | R2_05 | 92/92 | 0.42 | -61.50/-70.24 | 69.69/74.09 | 66.93/66.93 | SCARTATA |
| EXP-004 | V2_10 | 7/7 | 2.00 | 30.17/27.65 | 19.56/19.79 | 66.93/66.93 | INCONCLUSIVE |

- **EXP-002 — INCONCLUSIVE:** 11 validation trades in both cost cases, below the 30-trade floor. The selected configuration also had PF 0.98 and negative returns (-0.78% base; -3.79% doubled costs). Its drawdown was lower than buy-and-hold, but this does not offset the failed sample and return gates.
- **EXP-003 — SCARTATA:** 92 validation trades meet the operational count floor, but PF 0.42, returns -61.50%/-70.24%, and drawdowns 69.69%/74.09% all fail the corresponding pre-registered conditions. This is evidence against this frozen RSI specification in the tested windows, not a universal rejection of mean reversion.
- **EXP-004 — INCONCLUSIVE:** 7 validation trades, below the 30-trade floor. The selected result was positive in both cost cases (30.17%/27.65%), PF 2.00/1.89, and drawdown 19.56%/19.79% below the 66.93% buy-and-hold drawdown. These descriptive results do not meet the sample gate and do not establish an edge.
- **Diagnostics:** all 24 strategy executions had zero rejected orders and ended flat. Costs, fill counts, exposure and final equity are retained in the ignored local result JSON. The daily-bar fill model still assumes full fills and uses fixed cost estimates; the current quantity-filter snapshot is not a history of past exchange rules.
- **Attribution/licensing:** these derived metrics originate from Binance Vision and are attributed under the dataset terms already cited in EXP-001; they remain within CC BY-NC-SA 4.0 scope. No raw market files or result JSON are published. No project-wide software license is selected by this update.
- **Local reproducibility:** run `python -B backtest.py --experiment TRL-003 --dataset-dir data/binance/spot/monthly/klines/BTCUSDT/1d --output data/binance/spot/monthly/klines/BTCUSDT/1d/TRL-003-results.json`. Result JSON SHA-256: `7DF1C4FDB9FFE55B5BD7EC0E732D5F9E91412164F7A31CA3F0AD924028D9EC14`. Engine SHA-256 used in the run: `F4EDB391CEE87B9002937F6FAA90A0CA61E7A1C029F524CF13F137C7A7E1756C`. Raw data and output JSON are ignored by Git.
- **Decision/STOP:** EXP-003 is SCARTATA; EXP-002 and EXP-004 are INCONCLUSIVE; no strategy qualifies as a preliminary candidate. No final test was opened, no paper/forward trading or account activity was started, and no further variants or experiments are authorized by this order.

## TRL-004 frozen protocol (recorded before ETH data/results)

- **Initial state:** 2026-11-05; canonical workspace `E:\EA Tester`; branch `main`; clean starting HEAD `c69941bea61475c950c782f85708452c921573de`. Prior experiment sections and results are historical records and will not be edited. This section is an append-only second-instrument check.
- **Question:** do the already-selected BTCUSDT configurations D20_10 (EXP-002) and V2_10 (EXP-004) show similar economic behavior on ETHUSDT, without any retuning? EXP-003 is excluded because it was SCARTATA in TRL-003. No new strategy or parameter choice is permitted.
- **Fixed rules:** use the existing `make_exp_strategy_policy` implementations directly: EXP-002 entry close strictly above the prior 20 completed highs, exit close strictly below the prior 10 completed lows; EXP-004 positive close-to-close shock at least 2.0 times mean true range over the prior 14 completed bars, exit after 10 completed held bars. Current bar is excluded from channel/ATR reference as already implemented. Signal at completed UTC close; execute next UTC open. Long-only, one cash-funded position, no leverage, no position carry across windows, terminal close liquidation when accepted.
- **Market/data:** Binance Vision Spot ETHUSDT 1d UTC, exact requested coverage 2018-01-01 through 2025-12-31. Download only the 96 monthly klines archives and their official SHA-256 sidecars into the existing canonical `data/binance/spot/monthly/klines/ETHUSDT/1d` location. Save one symbol-specific manifest and one current public `exchangeInfo` filter snapshot in that same ignored directory. Do not publish raw data. Stop before economic evaluation if any required month/checksum is absent or any critical timestamp, calendar, checksum, ZIP, or OHLC validation fails. Current exchange filters are only a present-day simulation constraint; historical changes are unknown.
- **Windows:** separate simulations for 2018-01-01–2021-12-31 (1,461 sessions), 2022-01-01–2023-12-31 (730), and 2024-01-01–2025-12-31 (731). Each starts with 10,000 USDT and flat cash. Causal warm-up may use only preceding bars from this ETH dataset; no position or equity carries. Run every strategy, window, and cost case in one invocation so results from an early window cannot drive a later choice. Do not produce a combined aggregate return; independent window resets do not define one coherently compounded portfolio under this protocol.
- **Costs and benchmark:** same as TRL-003: base commission 10 bps per fill, full spread 2 bps and slippage 3 bps per side; doubled stress 20/4/6 bps. Model ETHUSDT quantity/notional constraints from its saved current exchangeInfo snapshot using the existing constraint logic. Benchmark each window with independently started ETHUSDT buy-and-hold, same capital, costs, and constraints. Report strategy-minus-benchmark return in percentage points for every window/cost case.
- **Required economic outputs:** for both strategies, each of the three windows, and both cost cases, record net return (not annualized), profit factor, maximum daily-close drawdown, completed trades, expectancy, win rate, close-based exposure, costs, final equity, fills/rejections/terminal position, benchmark return/drawdown/costs, and return difference versus benchmark. Retain local trade-level records. Trade percentiles use linear interpolation over sorted net P&L values at position (n-1)*p; report null percentiles when there are no trades. Summarize the trade distribution with count of winners/losers, median, 5th/95th percentiles, best/worst net trade, and top-one/top-three winner shares of the sum of positive trade P&L; null where no trades/winners. These concentration measures are descriptive, not inferential.
- **Predeclared interpretation, per period:** fewer than 30 completed trades in either cost case is **INCONCLUSIVE** for that strategy-period. At 30 or more in both cases, any non-positive net return or PF <= 1 in either case means the configuration does not pass the economic check for that period. Preliminary favorable historical evidence requires at least 30 in both cases, positive return and PF > 1 in both cases, and maximum drawdown below the corresponding buy-and-hold drawdown in both cases. This is not a promotion criterion or evidence of future profitability.
- **Cross-instrument comparison:** compare only the same frozen configuration and matching 2018-2021 and 2022-2023 windows against the already-recorded BTC TRL-003 results; do not rerun BTC. BTC EXP-002/EXP-004 results for 2024-2025 do not exist under the frozen research, so make no same-strategy BTC comparison for that period. BTC and ETH returns are not independent because the markets are correlated and share the venue/data source.
- **Implementation and verification:** adapt only the existing loader, symbol-specific filenames/filter validation, and existing run path. Keep the same engine, costs, accounting, metrics and benchmark; add only necessary ETH-focused synthetic tests. Run the existing complete suite before any ETH economic evaluation. No new dependencies, second engine, registry, service, branch, or data source.
- **Source/license:** Binance Public Data Spot monthly klines and official `.CHECKSUM` sidecars; Binance Vision Dataset Terms v1.0 (2026-08-26) permit personal non-production historical backtesting for non-commercial research and require attribution plus CC BY-NC-SA 4.0 for redistributed derivatives. Raw ETH data and trade-level results remain local/ignored. Sources: [Binance Public Data format and timestamp notes](https://github.com/binance/binance-public-data/blob/master/README.md), [Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md), [Binance Spot filters](https://github.com/binance/binance-spot-api-docs/blob/master/filters.md).


## TRL-004 results (single frozen ETHUSDT evaluation)

- **Esecuzione:** 2026-11-05, dopo 30/30 test sintetici/regressione e ricaricamento QC del dataset. Un solo avvio ha calcolato 12 esecuzioni strategia (2 configurazioni x 3 finestre x 2 costi) e 6 benchmark (3 finestre x 2 costi). I parametri non sono stati cambiati dopo aver visto i risultati. Nessun backtest BTC è stato ripetuto.
- **Dati e provenienza:** Binance Vision Spot ETHUSDT 1d UTC, 96 archivi mensili, 2.922 barre dal 2018-01-01 al 2025-12-31; 2.557 righe con timestamp in millisecondi e 365 in microsecondi. Manifest SHA-256: `3b8dafafd7c1f2f7a30fbc25be4802d3bfdf2d3008cb7f38cf577b42e994ffbb`. Snapshot pubblico exchangeInfo, acquisito `2026-11-05T12:52:31.983861Z`, SHA-256: `3caa914a54d00752143074dff767a59c72a21c55b87a27ba7794ab194bc6fd69`. Filtri applicati: quantità min/step 0.0001 ETH, max 3296.98395916 ETH, notional minimo 5 USDT.
- **Protocollo eseguito:** D20_10 (EXP-002) e V2_10 (EXP-004), regole congelate sopra; finestre indipendenti da 10.000 USDT, warm-up solo storico e nessun capitale/posizione trasferiti. Commissioni/spread totale/slippage per lato: 10/2/3 bps base e 20/4/6 bps stress. Ogni benchmark compra ETH alla prima apertura e liquida alla chiusura finale con gli stessi costi e vincoli. Rendimento non annualizzato; drawdown su equity a chiusura giornaliera. Nessun rendimento aggregato è calcolato tra finestre con capitale resettato.

### Metriche strategia e benchmark

| Strategia/config. | Finestra | Caso costi | Esito | Rendimento % | B&H % | Delta pp | PF | Max DD % (B&H %) | Trade | Expectancy USDT | Win % | Esposizione % | Costi USDT | Equity finale USDT |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EXP-002 D20_10 | 2018-2021 sviluppo BTC | base | INCONCLUSIVE | 1275.95 | 400.12 | 875.83 | 23.56 | 58.54 (93.97) | 17 | 7505.61 | 64.71 | 43.26 | 1355.24 | 137595.33 |
| EXP-002 D20_10 | 2018-2021 sviluppo BTC | stress x2 | INCONCLUSIVE | 1211.99 | 398.72 | 813.27 | 22.06 | 59.57 (93.97) | 17 | 7129.38 | 52.94 | 43.26 | 2611.51 | 131199.44 |
| EXP-002 D20_10 | 2022-2023 validazione BTC | base | INCONCLUSIVE | -5.91 | -38.10 | 32.19 | 0.91 | 47.69 (74.00) | 11 | -53.71 | 36.36 | 33.56 | 275.40 | 9409.23 |
| EXP-002 D20_10 | 2022-2023 validazione BTC | stress x2 | INCONCLUSIVE | -8.76 | -38.27 | 29.51 | 0.87 | 48.92 (74.00) | 11 | -79.65 | 36.36 | 33.56 | 542.75 | 9123.85 |
| EXP-002 D20_10 | 2024-2025 estensione | base | INCONCLUSIVE | -29.10 | 29.86 | -58.97 | 0.68 | 47.97 (63.75) | 13 | -223.87 | 46.15 | 33.65 | 319.13 | 7089.63 |
| EXP-002 D20_10 | 2024-2025 estensione | stress x2 | INCONCLUSIVE | -31.64 | 29.50 | -61.14 | 0.65 | 49.62 (63.75) | 13 | -243.37 | 38.46 | 33.65 | 626.94 | 6836.21 |
| EXP-004 V2_10 | 2018-2021 sviluppo BTC | base | INCONCLUSIVE | 63.44 | 400.12 | -336.68 | 2.40 | 25.51 (93.97) | 13 | 487.99 | 53.85 | 8.90 | 447.76 | 16343.84 |
| EXP-004 V2_10 | 2018-2021 sviluppo BTC | stress x2 | INCONCLUSIVE | 57.60 | 398.72 | -341.13 | 2.25 | 25.72 (93.97) | 13 | 443.05 | 53.85 | 8.90 | 877.52 | 15759.66 |
| EXP-004 V2_10 | 2022-2023 validazione BTC | base | INCONCLUSIVE | 10.57 | -38.10 | 48.67 | 1.77 | 17.35 (74.00) | 6 | 176.16 | 66.67 | 8.22 | 193.35 | 11056.95 |
| EXP-004 V2_10 | 2022-2023 validazione BTC | stress x2 | INCONCLUSIVE | 8.73 | -38.27 | 47.00 | 1.60 | 18.04 (74.00) | 6 | 145.46 | 50.00 | 8.22 | 383.43 | 10872.74 |
| EXP-004 V2_10 | 2024-2025 estensione | base | INCONCLUSIVE | 25.06 | 29.86 | -4.80 | 2.25 | 17.12 (63.75) | 6 | 417.69 | 66.67 | 8.21 | 192.52 | 12506.17 |
| EXP-004 V2_10 | 2024-2025 estensione | stress x2 | INCONCLUSIVE | 22.98 | 29.50 | -6.52 | 2.13 | 17.47 (63.75) | 6 | 382.96 | 66.67 | 8.21 | 381.60 | 12297.79 |

| Benchmark ETH buy-and-hold | Finestra | Caso costi | Rendimento % | Max DD % | Costi USDT | Equity finale USDT |
|---|---|---|---:|---:|---:|---:|
| ETHUSDT | 2018-2021 sviluppo BTC | base | 400.12 | 93.97 | 84.08 | 50012.29 |
| ETHUSDT | 2018-2021 sviluppo BTC | stress x2 | 398.72 | 93.97 | 167.89 | 49872.26 |
| ETHUSDT | 2022-2023 validazione BTC | base | -38.10 | 74.00 | 22.66 | 6189.87 |
| ETHUSDT | 2022-2023 validazione BTC | stress x2 | -38.27 | 74.00 | 45.26 | 6172.57 |
| ETHUSDT | 2024-2025 estensione | base | 29.86 | 63.75 | 32.19 | 12986.39 |
| ETHUSDT | 2024-2025 estensione | stress x2 | 29.50 | 63.75 | 64.28 | 12950.09 |

### Distribuzione trade e concentrazione

| Strategia/config. | Finestra | Caso costi | Vinti/persi/zero | Mediana USDT | P05 USDT | P95 USDT | Migliore/peggiore USDT | Quota top-1/top-3 vincitori % |
|---|---|---|---:|---:|---:|---:|---:|---:|
| EXP-002 D20_10 | 2018-2021 sviluppo BTC | base | 11/6/0 | 781.00 | -1436.37 | 42395.96 | 47666.42/-1467.28 | 35.77/82.53 |
| EXP-002 D20_10 | 2018-2021 sviluppo BTC | stress x2 | 9/8/0 | 750.85 | -1451.90 | 40536.98 | 45795.58/-1489.15 | 36.07/82.74 |
| EXP-002 D20_10 | 2022-2023 validazione BTC | base | 4/7/0 | -695.19 | -1480.77 | 1930.39 | 2108.92/-1946.36 | 35.86/87.32 |
| EXP-002 D20_10 | 2022-2023 validazione BTC | stress x2 | 4/7/0 | -701.76 | -1493.10 | 1870.28 | 2025.12/-1961.53 | 35.65/87.55 |
| EXP-002 D20_10 | 2024-2025 estensione | base | 6/7/0 | -564.22 | -1928.11 | 1784.51 | 1994.82/-1991.91 | 32.68/80.23 |
| EXP-002 D20_10 | 2024-2025 estensione | stress x2 | 5/8/0 | -580.15 | -1912.43 | 1733.55 | 1918.50/-2004.67 | 32.76/81.00 |
| EXP-004 V2_10 | 2018-2021 sviluppo BTC | base | 7/6/0 | 31.26 | -1854.92 | 3356.74 | 4884.01/-2853.67 | 44.89/84.00 |
| EXP-004 V2_10 | 2018-2021 sviluppo BTC | stress x2 | 7/6/0 | 1.67 | -1849.66 | 3223.58 | 4720.42/-2803.56 | 45.47/85.04 |
| EXP-004 V2_10 | 2022-2023 validazione BTC | base | 4/2/0 | 105.34 | -713.20 | 1227.66 | 1344.52/-738.74 | 55.28/99.45 |
| EXP-004 V2_10 | 2022-2023 validazione BTC | stress x2 | 3/3/0 | 71.03 | -737.89 | 1191.68 | 1306.68/-764.44 | 56.42/100.00 |
| EXP-004 V2_10 | 2024-2025 estensione | base | 4/2/0 | 653.18 | -1269.97 | 1601.51 | 1602.63/-1539.47 | 35.56/95.13 |
| EXP-004 V2_10 | 2024-2025 estensione | stress x2 | 4/2/0 | 621.15 | -1286.47 | 1551.41 | 1554.71/-1552.57 | 35.84/95.66 |

Percentili calcolati con interpolazione lineare sui P&L netti per trade ordinati, in posizione `(n-1)*p`; `—` indica metrica non definita. Le quote top-1/top-3 sono percentuali del P&L positivo complessivo e sono descrittive, non inferenziali.

### Confronto con le metriche BTC già registrate in TRL-003

| Esperimento/config. | Finestra | BTC rendimento base/stress % | ETH rendimento base/stress % | BTC PF base/stress | ETH PF base/stress | BTC DD base/stress % | ETH DD base/stress % | Trade BTC / ETH base-stress |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EXP-002 D20_10 | 2018-2021 | 861.61/822.06 | 1275.95/1211.99 | 2.83/2.78 | 23.56/22.06 | 37.66/38.09 | 58.54/59.57 | 15/15; 17/17 |
| EXP-002 D20_10 | 2022-2023 | -0.78/-3.79 | -5.91/-8.76 | 0.98/0.92 | 0.91/0.87 | 39.19/39.96 | 47.69/48.92 | 11/11; 11/11 |
| EXP-004 V2_10 | 2018-2021 | 103.25/94.89 | 63.44/57.60 | 4.63/4.27 | 2.40/2.25 | 21.74/21.96 | 25.51/25.72 | 15/15; 13/13 |
| EXP-004 V2_10 | 2022-2023 | 30.17/27.65 | 10.57/8.73 | 2.00/1.89 | 1.77/1.60 | 19.56/19.79 | 17.35/18.04 | 7/7; 6/6 |

Non esistono risultati BTC D20_10/V2_10 2024-2025 nella ricerca congelata; nessun confronto o rerun BTC è stato effettuato per tale finestra. BTC ed ETH sono mercati correlati e condividono venue/fonte, quindi ETH è una verifica su un secondo strumento ma non un campione di mercato indipendente.

### Decisione, limiti e riproducibilità

- Tutte le sei combinazioni strategia-finestra sono **INCONCLUSIVE** secondo la soglia predefinita: 17/11/13 trade per D20_10 e 13/6/6 per V2_10, sempre sotto 30 in entrambe le ipotesi di costo. Nessuna configurazione è promossa o candidata al paper trading.
- EXP-002 perde in entrambe le ipotesi di costo nel 2022-2023 e nel 2024-2025; nel 2024-2025 sottoperforma ETH buy-and-hold di 58.97/61.14 punti percentuali. Il risultato molto alto 2018-2021 non supera il gate campionario e il top-3 trade rappresenta 82.53/82.74% del P&L positivo.
- EXP-004 è positiva in tutte le finestre ETH, ma nel 2018-2021 è molto sotto buy-and-hold (-336.68/-341.13 pp), nel 2022-2023 è sopra il benchmark in un periodo ribassista (+48.67/+47.00 pp), e nel 2024-2025 resta sotto il benchmark (-4.80/-6.52 pp). I campioni sono 13/6/6 trade e il top-3 assorbe 84.00-100.00% del P&L positivo a seconda di finestra/costi: evidenza insufficiente.
- Tutte le 12 simulazioni strategiche hanno zero ordini rifiutati e terminano flat; i record completi trade-level sono nel JSON locale. Il motore usa costi stimati, riempimenti completi e il filtro quantità/notional osservato soltanto il 2026-11-05; non ricostruisce spread, slippage, filtri o liquidità storici. Nessun paper trading, replay prospettico, collegamento a conti o ordine è stato avviato.
- Dati grezzi e JSON con record trade restano locali e ignorati da Git. I risultati derivati pubblicati sono attribuiti a Binance Vision e restano soggetti ai termini CC BY-NC-SA 4.0 indicati in TRL-004 frozen protocol; nessuna licenza software generale è scelta. Fonti: [Binance Public Data README](https://github.com/binance/binance-public-data/blob/master/README.md), [Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).
- **File e hash:** JSON locale `data/binance/spot/monthly/klines/ETHUSDT/1d/TRL-004-results.json`; SHA-256 `DF5D51A9890BABEC9A627E3E8667399F58DC7A171CAC39E1DB0BA2BDBEBD62B6`. Motore registrato dalla run: SHA-256 `FD3CBFEF3E03BD02158395303CCC4A8960EEF795B87DF78B9E745A048565A644`. Riproducibilità: `python -B backtest.py --experiment TRL-004 --dataset-dir data/binance/spot/monthly/klines/ETHUSDT/1d --output data/binance/spot/monthly/klines/ETHUSDT/1d/TRL-004-results.json`.
- **Decisione/STOP:** ciclo TRL-004 completato tecnicamente; risultati economici ETH tutti inconcludenti per numerosità, nessuna promozione. Nessun TRL-005 o paper trading è autorizzato da questo ordine.


## TRL-004 result diagnostics supplement

- **Strategy fills by window (base/stress):** EXP-002 D20_10 = 34/34 (2018-2021), 22/22 (2022-2023), 26/26 (2024-2025); EXP-004 V2_10 = 26/26, 12/12, 12/12 in the same window order. All 12 strategy cases had zero rejected orders and ended with zero open quantity.
- **Benchmark fills:** ETH buy-and-hold had 2 fills in each of the 6 window/cost cases, zero rejected orders, and zero terminal open quantity. These diagnostics are also retained in the ignored local result JSON referenced above.


## TRL-005 frozen protocol (recorded before H4 economic evaluation)

- **Starting state:** 2026-11-05; canonical workspace `E:\EA Tester`; branch `main`; starting HEAD `6f7bc87fd65595e54b94b0bbbb16a168404cc21a`; working tree verified clean. TRL-001–TRL-004 are closed and will not be rerun or rewritten. No EXP-005/EXP-006 IDs were present in the register before this protocol.
- **Research question:** test two distinct H4 mechanisms on BTCUSDT Spot: (1) continuation after volatility contraction with an expanding, volume-confirmed breakout; (2) short-horizon reversal after an unusually large, high-quote-volume negative shock. This is not a transfer of the selected D1 parameter configurations. Four fixed configurations total; no additional variants or broad search.
- **Market/data:** BTCUSDT Spot, Binance Vision monthly klines, `4h` interval, UTC, 2018-01-01 00:00 through 2023-12-31 20:00 open times only. Archive path is the existing canonical symbol/timeframe structure `data/binance/spot/monthly/klines/BTCUSDT/4h/`; expected 72 monthly archives, 2,191 days x 6 bars = 13,146 bars. Open times must be exactly 00:00, 04:00, 08:00, 12:00, 16:00, and 20:00 UTC each complete day; each close time must be open + 4 hours - 1 millisecond for the historical millisecond data. Verify official SHA-256 sidecars, ZIP/CSV contents, timestamps, UTC alignment, strict ordering, complete grid, duplicates, OHLC, non-negative volumes, and 12-column row shape. No 2024–2025 data may be downloaded, loaded, or evaluated. Reuse the already-canonical BTC exchange-filter snapshot under the 1d dataset; its rules are present-day constraints, not historical rules.
- **Windows and capital:** development 2018-01-01 00:00–2021-12-31 20:00 UTC (8,766 bars); validation 2022-01-01 00:00–2023-12-31 20:00 UTC (4,380 bars). Each window is a separate 10,000 USDT simulation starting flat, with no position or equity transferred. Validation may receive development bars solely as causal indicator warm-up; no position is carried. Development phase must load/run only development bars. Do not calculate a combined return across independently reset windows.
- **Shared execution/risk:** signals are formed only after a bar closes and execute at the next 4h bar open. No intrabar stop/target model is used. Long-only, cash-funded, one position maximum, no pyramiding, no shorting or leverage. Each entry uses the existing engine's cash-based sizing, lot/notional constraints and commission accounting. Maximum exposure is the available simulation cash; risk is limited to that cash-funded position, and a severe move may lose nearly all of it. Any strategy still open at the end is liquidated at the last bar close when exchange constraints permit. Insufficient warm-up, missing usable quote-volume history, an open position, or no signal are non-operating conditions.
- **EXP-005 — Volatility-compression breakout continuation.** Rationale: a compressed realized range followed by a close breakout with expanding quote volume may indicate price discovery continuing as resting liquidity is consumed; it should fail in false breakouts, mean-reverting ranges, or when volume marks exhaustion instead of continuation. For each closed bar t, compute true range from that bar's high/low and previous close. Require mean TR of the six completed bars immediately before t to be <= 0.65 times mean TR of the 24 completed bars immediately preceding those six. Also require close[t] strictly above the highest high of the previous L completed bars and quote_volume[t] >= 1.25 times the mean quote volume of the previous 24 completed bars. Enter long at next open. Exit on a close strictly below the minimum low of the previous six completed bars, or after 18 completed bars in position; execute the signal at next open. Configurations, identical except for breakout lookback L: **EXP-005 C12** (L=12 H4 bars) and **EXP-005 C24** (L=24). No other threshold or exit variation is allowed.
- **EXP-006 — High-volume negative-shock reversal.** Rationale: an unusually large negative close-to-close move accompanied by exceptional quote turnover may reflect short-lived forced selling/liquidity overshoot followed by replenishment; it should fail in persistent sell-offs, news repricing, and when high volume confirms continuation rather than exhaustion. For each closed bar t, require close[t]/close[t-1]-1 <= -k x mean(TR of the previous 24 completed bars)/close[t-1], and quote_volume[t] >= 2.0 x mean quote volume of the previous 24 completed bars. Enter long at next open. Exit when close[t] >= the arithmetic mean of the previous six completed closes, or after 12 completed bars in position; execute the signal at next open. Configurations, identical except k: **EXP-006 S20** (k=2.0) and **EXP-006 S25** (k=2.5). No other threshold or exit variation is allowed.
- **Position/risk details:** one position at a time; no partial exits, no leverage, no stop/target inside an H4 candle, no re-entry while a position is open. All rules depend only on completed current/prior bars. Trade duration is measured from entry fill time through exit fill time in H4 bars and hours. A terminal liquidation is valued at the bar close, not the following open.
- **Costs and references:** base commission 10 bps per fill, total spread 2 bps (half per side), slippage 3 bps per side; stress doubles each to 20/4/6 bps. These are fixed assumptions, not measured historical execution costs. For each window and cost case, calculate BTCUSDT buy-and-hold from first bar open to final bar close with the same starting capital, constraints, and costs. Also report uninvested cash as a 0% return, 0% drawdown, zero-cost reference.
- **Fitting and development selection:** exactly four configurations are tested on development under base and stress costs (eight strategy runs); only the two window-matched buy-and-hold benchmarks are required. A configuration is eligible for its hypothesis's single validation slot only if it has at least 30 completed trades in both cost cases, positive net return in both, base profit factor > 1, and base maximum drawdown below base buy-and-hold drawdown. The 30-trade floor is an operational screen, not statistical significance. If both configurations of a hypothesis pass, select the greater stress-cost net return; ties go to lower stress-cost drawdown, then lexicographically earlier config ID. If neither passes, do not validate that hypothesis. Record every development attempt and selection/rejection before opening any validation data; commit/push the development record before validation.
- **Validation gates:** evaluate each selected configuration exactly once in 2022–2023, under base and stress costs, with only prior development bars for warm-up and fresh 10,000 USDT. Preliminary favorable historical evidence requires at least 30 completed trades in both cost cases, positive net return and PF > 1 in both, and max drawdown below buy-and-hold in both. Fewer than 30 trades is **INCONCLUSIVE**; with sufficient sample, failure of any economic gate is **SCARTATA**. Passing these gates is historical preliminary evidence only, not proof of future profitability or promotion to paper trading. The project has already observed 2022–2023 in D1 research, so this is not a laboratory-wide blind holdout.
- **Metrics/outputs:** net (non-annualized) return, final equity, close-to-close H4 maximum drawdown, profit factor, expectancy, completed trades, win rate, exposure, total costs, fill/rejection/terminal-position diagnostics, per-trade duration (min/median/mean/max bars and hours), trade P&L distribution and top-one/top-three positive-P&L concentration, benchmark return/drawdown/costs, cash reference, and return difference versus each benchmark. Retain full trade records only in ignored local result JSON. All runs must be deterministic and use the single existing engine.
- **Technical gate before any economic run:** extend the existing parser/loader/Bar timeline minimally for H4 while preserving default D1 behavior; verify full existing D1 suite, H4 timestamp grid and six-bars-per-day boundary transitions, no future-bar use, next-open execution, synthetic rules for both hypotheses/config dimensions, accounting/cost/equity reconciliation, H4 benchmark and reproducibility. No new dependency, engine, data archive, registry, branch or service.
- **Source and use limits:** official Binance Vision Spot klines and official `.CHECKSUM` files. Binance documents `4h` support, monthly archives, twelve kline columns, and the Spot timestamp precision change from 2025; this order ends in 2023. The current Binance Vision terms allow personal non-production historical backtesting for non-commercial research; any public derived results require Binance Vision attribution and CC BY-NC-SA 4.0. Do not publish raw market files or trade-level output. Sources: [Binance Public Data README](https://github.com/binance/binance-public-data/blob/master/README.md), [Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).
- **Boundaries:** no 2024–2025 data or final test, no paper/demo/live activity, no account connection, no VPS/service, no paid compute, no GPU, no external project changes, no repository/branch duplication, no additional configurations, and no power-state action.


## TRL-005 data-integrity gate: BLOCKED before economic fitting

- **Checkpoint:** 2026-11-05, after protocol freeze `fadcb94d521af9e52f80558850c279798fb19c32` and before any economic run. The canonical Binance Vision Spot BTCUSDT `4h` archive for February 2018 was fetched from the official monthly endpoint and checked against its official `.CHECKSUM`; the SHA-256 matched (`35158247eb814e49ad96bab8c0c7c073b57ddc12b462f0176d1beeda7cefefd2`) and ZIP CRC validation passed.
- **Grid defect:** the CSV contains 161 bars where the frozen UTC calendar requires 168. The following expected open times are absent: `2018-02-08T04:00:00Z`, `08:00Z`, `12:00Z`, `16:00Z`, `20:00Z`, and `2018-02-09T00:00:00Z`, `04:00Z`. This breaks the mandatory six-bars-per-day continuous grid for 2018-01-01 through 2023-12-31.
- **Acquisition status:** stopped at the first failing month. Only the January 2018 archive and checksum were saved locally under the ignored `data/` tree; no dataset manifest was produced. The remaining months and the complete 13,146-bar calendar are unverified. No gap was interpolated or filled.
- **Economic status:** no development backtest ran; 0 of 4 frozen configurations were economically evaluated; there is no development selection. Validation, final test, and paper trading were not opened. The data gate fails, so the economic phase is **BLOCKED**.
- **Technical preparation:** the existing engine has H4 UTC parsing/loading and the four frozen signal configurations; the full local suite passed (35 tests) and `python -B backtest.py --help` completed. This is technical evidence only, not a strategy result.
- **Decision:** do not change the frozen dates, fill the missing candles, or substitute another feed within this order. Resumption requires an explicitly revised data source or research period and a new frozen protocol. No profitability claim or candidate is made.
- **Attribution and publication:** the source is [Binance Vision Spot public data](https://github.com/binance/binance-public-data); derived source observations in this record are attributed to Binance Vision and are subject to the dataset terms, including CC BY-NC-SA 4.0 for redistributed derivatives. No raw OHLC archives or trade-level output are published. The repository's general software license remains undecided.
