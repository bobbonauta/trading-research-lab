# Trading Research Lab

Trading Research Lab is an independent quantitative research project for proposing falsifiable trading hypotheses, turning them into explicit rules, and evaluating them with reproducible data and deterministic calculations. The aim is to find repeatable evidence, including evidence that rejects a strategy. Profitability is not presumed.

## Current verified state — 2026-11-04

This public repository contains the permanent directives, one experiment register, a minimal backtest prototype, and synthetic technical tests. It has no verified market dataset and no market-data backtest results.

The initial reconnaissance found Python 3.11.5 with NumPy 1.26.4, pandas 2.1.4, Polars 1.38.1, and SciPy 1.15.3 available on the host. The checked common backtest engines were not installed. The current engine in `backtest.py` uses only the Python standard library. Eight tests in `test_backtest.py` pass on synthetic bars; they do not verify market data, trading costs, or strategy performance.

No market-data source or dataset has been verified for this project. Local MetaQuotes terminal data directories exist, but their data provenance, coverage, quality, and redistribution rights have not been established. No matching MetaTrader, cTrader, or TradingView process was detected during reconnaissance. No demo or paper account was connected or verified.

EXP-001 is recorded as NON VERIFICATA and blocked before a market-data backtest because there is no verified data source or dataset and market-specific costs are not frozen. Its SMA crossover remains a proposal. No backtest or paper-trading performance results exist. No live or demo orders have been sent. There are no GitHub Actions, deployments, or trading-account integrations.

## Prototype engine scope

The engine implements the proposed daily SMA(20)/SMA(100) crossover with signals evaluated on completed bars and orders attempted at the next bar open. It supports one long position, whole units, cash-only sizing, commission, spread, slippage, rejected orders when cash cannot buy one unit, and liquidation at the final bar close. It rejects missing, inconsistent, non-finite, or out-of-order OHLC bars.

It assumes full fills at the modeled price. It does not simulate partial fills, order-book liquidity, margin, dividends or corporate-action adjustments, broker-specific sessions, or a benchmark. No instrument-specific cost or data convention has been selected. Synthetic test fixtures are not market data.

## Research workflow

The intended chain is:

**Hypothesis → Formal strategy specification → Verified data → Deterministic backtest → Chronological out-of-sample validation → Robustness checks → Selection → Authorized paper trading → Evaluation.**

The first complete market experiment should reuse one canonical data source, one engine, and this single experiment register. Components that do not yet exist are requirements, not claims of current capability.

## Methodology

- State a falsifiable economic hypothesis and a comparable baseline before examining results.
- Choose the instrument and data source before evaluating strategy performance. Record source, interval, timestamps, timezone, sessions, adjustments, gaps, and a file hash where applicable.
- Freeze the market, timeframe, entry and exit rules, sizing, risk limits, costs, benchmark, and evaluation criteria before the final test.
- Use only information available at decision time. Generate signals on closed bars and execute no earlier than the next bar. Record assumptions for spreads, commissions, slippage, gaps, and unfilled orders.
- Keep development, validation, and final test periods chronological. Use a 60/20/20 split only when the verified sample is large enough; do not repeatedly tune on the final period.
- Compare results with a compatible benchmark. Report costs, risk, exposure, drawdown, trade counts, limitations, and negative outcomes. Do not infer future returns from historical performance.
- Use deterministic code for numerical results. Any synthetic checks must be identified as synthetic and kept separate from market-data results.
- Paper trading requires a frozen candidate, documented risk limits, and a separate explicit authorization. Research authorization does not permit live trading.

## EXP-001 proposal

The starting hypothesis is that price persistence may produce a statistical advantage after realistic costs, but the effect may be absent or regime-dependent. The proposed rule is long-only: enter when SMA(20) crosses above SMA(100) and exit when SMA(20) crosses below SMA(100), on daily bars. It has not been run on market data. The instrument, verified dataset, market-specific costs, benchmark, and final evaluation periods still need to be selected and frozen before a market test.

See [EXPERIMENTS.md](./EXPERIMENTS.md) for its recorded state and [test_backtest.py](./test_backtest.py) for synthetic technical checks.

## Data, security, and licensing

Do not commit credentials, personal configuration, local caches, virtual environments, or market data whose redistribution rights have not been verified. The root .gitignore excludes common secret files, local environments, caches, temporary files, and raw tabular market data by default. Record data provenance and rights before adding any data to the public repository.

No software license has been selected. No LICENSE file is included; the owner must choose a license before granting reuse rights.

## Project directives

The permanent operating and scientific rules are in [TRADING_RESEARCH_LAB_DIRETTIVE_PERMANENTI.md](./TRADING_RESEARCH_LAB_DIRETTIVE_PERMANENTI.md). They govern scope, data handling, validation, risk, authorization, and reporting.