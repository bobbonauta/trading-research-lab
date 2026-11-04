# Trading Research Lab

Trading Research Lab is an independent quantitative research project for proposing falsifiable trading hypotheses, turning them into explicit rules, and evaluating them with reproducible data and deterministic calculations. The aim is to find repeatable evidence, including evidence that rejects a strategy. Profitability is not presumed.

## Current verified state — 2026-11-04

This initial public snapshot contains project documentation and one experiment record. It does not yet contain strategy code, backtest code, or a canonical market dataset. Before the first commit, the authorized workspace contained only the permanent project directives and no repository, strategy code, experiment registry, or canonical market dataset. The reconnaissance found Python 3.11.5 with NumPy, pandas, Polars, and SciPy available on the host; the checked common backtest packages were not installed. No backtest engine has been selected or implemented.

No market-data source or dataset has been verified for this project. Local MetaQuotes terminal data directories exist, but their data provenance, coverage, and redistribution rights have not been established. No matching MetaTrader, cTrader, or TradingView process was detected during reconnaissance. No demo or paper account was connected or verified.

EXP-001 is recorded as NON VERIFICATA and blocked before execution because no market-data source, dataset rights, or backtest engine is verified. The SMA crossover remains a proposal; no instrument, costs, or complete execution rules are frozen. No backtest or paper-trading results exist in this repository. No live or demo orders have been sent. There are no GitHub Actions, deployments, or trading-account integrations.

## Research workflow

The intended chain is:

**Hypothesis → Formal strategy specification → Verified data → Deterministic backtest → Chronological out-of-sample validation → Robustness checks → Selection → Authorized paper trading → Evaluation.**

The first implementation should reuse one canonical data source, one backtest engine, and one experiment register. Components that do not yet exist are requirements, not claims of current capability.

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

The authorized starting hypothesis is a long-only trend-following rule using a 20-period and 100-period simple moving average crossover on daily bars. It has not been executed. An instrument, verified dataset, execution assumptions, and cost schedule still need to be established and frozen before any market-data test. No parameter may be changed after observing the final test results.

## Data, security, and licensing

Do not commit credentials, personal configuration, local caches, virtual environments, or market data whose redistribution rights have not been verified. The root .gitignore excludes common secret files, local environments, caches, temporary files, and raw tabular market data by default. Record data provenance and rights before adding any data to the public repository.

No software license has been selected. No LICENSE file is included; the owner must choose a license before granting reuse rights.

## Project directives

The permanent operating and scientific rules are in [TRADING_RESEARCH_LAB_DIRETTIVE_PERMANENTI.md](./TRADING_RESEARCH_LAB_DIRETTIVE_PERMANENTI.md). They govern scope, data handling, validation, risk, authorization, and reporting.