# Experiment register

Last updated: 2026-11-04

This is the single canonical experiment register for Trading Research Lab. No other experiments or strategy variants are recorded.

## EXP-001 — Daily long-only SMA crossover

- **State:** NON VERIFICATA; blocked before a market-data backtest. This is a prerequisite failure, not an economic rejection of the hypothesis.
- **Hypothesis:** price trends may persist long enough to produce a statistical advantage after realistic costs; any effect may be absent or regime-dependent.
- **Proposed rule:** on daily bars, enter long when SMA(20) crosses above SMA(100); exit when SMA(20) crosses below SMA(100). Signals use closed bars; orders are attempted at the next bar open. No short positions, leverage, or concurrent positions.
- **Sizing and risk mechanics in the prototype:** buy whole units using available cash only; one position at a time; no stop is used, so loss can reach the invested amount. Any future use must confirm this risk rule for the selected instrument.
- **Gap and order assumptions in the prototype:** next-bar open reference price, with modeled spread and slippage; assume full fills. Insufficient cash for one unit is recorded as a rejected order. Missing/inconsistent OHLC data stops the run. Any open position is liquidated at the final bar close.
- **Instrument:** not selected. Selection must precede viewing test results.
- **Data and provenance:** no canonical market dataset is present in the authorized workspace. MetaQuotes terminal data directories were detected, but source, coverage, quality, and redistribution rights were not verified. No market data was copied or published.
- **Development/validation/test periods:** not defined because no dataset has been verified. A chronological 60/20/20 split is only a proposal if sample size supports it.
- **Costs and benchmark:** not frozen for a market run. Spread, commissions, slippage, and a compatible benchmark must be defined. The synthetic cost test used 10 bps commission, 2 bps spread, and 1 bp slippage per side; these are test inputs only, not market assumptions.
- **Engine and code version:** `backtest.py`, SHA-256 `8570FE426700E16809802414F489DD424AA6BF87AF4035D790F3C48A237F6A97`; no external engine or package installation. The engine is a prototype and has no benchmark or market-data ingestion layer.
- **Technical checks:** `python -m unittest -v test_backtest` passed 8/8 synthetic tests on Python 3.11.5. Checks cover next-bar entry/exit timing, cost and P&L reconciliation, losing trades, no-trade periods, insufficient cash, missing/inconsistent data, and reproducibility. The first run failed because `fmean` was imported from `math`; the import was corrected and the full suite then passed.
- **Attempts/variants:** zero market-data backtests; one proposed rule; no tuning or parameter variants.
- **Results:** NOT RUN on market data. No P&L, performance, risk, benchmark, or trade metrics are available for a real instrument.
- **Decision:** do not run EXP-001 until a dataset and its use rights are verified and the instrument, costs, benchmark, and evaluation split are frozen. Do not treat synthetic checks as a measured strategy result.
- **Next required evidence:** approved data source, instrument and interval, provenance/quality checks, frozen cost and benchmark assumptions, and subsequent market-data validation.