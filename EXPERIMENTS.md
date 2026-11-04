# Experiment register

Last updated: 2026-11-04

This is the single canonical experiment register for Trading Research Lab. No other experiments or strategy variants are recorded.

## EXP-001 — Daily long-only SMA crossover

- **State:** NON VERIFICATA; blocked before backtest. This is a prerequisite failure, not an economic rejection of the hypothesis.
- **Hypothesis:** price trends may persist long enough to produce a statistical advantage after realistic costs; any effect may be absent or regime-dependent.
- **Proposed rule:** on daily bars, enter long when SMA(20) crosses above SMA(100); exit when SMA(20) crosses below SMA(100). Signals use closed bars; execution must occur no earlier than the next bar. No short positions, leverage, or concurrent positions are proposed.
- **Instrument:** not selected. Selection must precede viewing test results.
- **Sizing and risk rules:** not frozen. Position sizing, stop/protection rules, gap handling, unfilled-order behavior, and end-of-test liquidation must be specified before execution.
- **Data and provenance:** no canonical market dataset is present in the authorized workspace. MetaQuotes terminal data directories were detected, but source, coverage, quality, and redistribution rights were not verified. No market data was copied or published.
- **Development/validation/test periods:** not defined because no dataset has been verified. A chronological 60/20/20 split is only a proposal if sample size supports it.
- **Costs and benchmark:** not frozen. Spread, commissions, slippage, and a compatible benchmark must be defined before a run.
- **Engine and code version:** no backtest engine or experiment code exists. The initial repository commit contains documentation only.
- **Attempts/variants:** zero backtests; one proposed rule; no tuning or parameter variants.
- **Results:** NOT RUN. No P&L, performance, risk, or trade metrics are available.
- **Decision:** do not run EXP-001 until a dataset and its use rights are verified and all execution, cost, sizing, and evaluation rules are frozen. Do not treat this blocked record as a measured strategy result.
- **Next required evidence:** approved data source, instrument and interval, provenance/quality checks, frozen costs and execution assumptions, and a deterministic engine with technical checks.
