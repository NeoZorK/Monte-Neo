# Project Idea

## Why Monte-Neo?

Developing trading indicators is easy; developing **robust** indicators is hard. Most found strategies are the result of curve-fitting and over-optimization.

Monte-Neo was created to solve this by making **Monte Carlo Simulation** the first-class citizen in the development process. Instead of asking "Does it work in the past?", we ask:
- "Does it work if we shuffle the returns?"
- "Does it work if we add random noise?"
- "Does it work if we slightly change the parameters?"

## Core Principles

- **Robustness Over Profit**: A high-profit indicator that fails on shuffled data is worth nothing. We prioritize consistency and statistical significance.
- **Retail Accessibility**: Bring the advanced testing methodologies used by quant funds to the retail trading community.
- **Performance First**: Using JIT (Numba) and parallel processing to handle hundreds of thousands of simulations per hour.
- **Open Architecture**: Easy to add new indicators, metrics, and data sources.

## Goals

1. **Automate Robustness**: Make it impossible to create an indicator without passing MC tests.
2. **Speed up Iteration**: Allow users to test 100,000+ candidates in minutes.
3. **Professional Quality**: Provide institutional-grade metrics (Sharpe, Sortino, Drawdown analysis) for retail traders.
4. **Reproduceability**: Full support for config files and seeds to ensure every generation can be replicated.
