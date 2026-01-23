# Project Idea

## Why Monte-Neo?

Developing trading indicators is easy; developing **robust** indicators is hard. Most found strategies are the result of curve-fitting and over-optimization.

Monte-Neo was created to solve this by making **Monte Carlo Simulation** the first-class citizen in the development process. Instead of asking "Does it work in the past?", we ask:
- "Does it work if we shuffle the returns?"
- "Does it work if we add random noise?"
- "Does it work if we slightly change the parameters?"

## Goals

1. **Automate Robustness**: Make it impossible to create an indicator without passing MC tests.
2. **Speed up Iteration**: Allow users to test 100,000+ candidates in minutes.
3. **Professional Quality**: Provide institutional-grade metrics for retail traders.
