# Project Vision

1) **Professional Development Setup**: Act as an experienced senior developer, architect, and vibecoding specialist. Use best architectural practices:
    - Create `INDEX.md` (list of all files with paths and assignments), `CLAUDE.md`, `README.md`, `ROADMAP.md`, etc.
    - Architecture: Organized structure with `src/`, `docs/`, `tests/`, `scripts/` folders and clear subfolders.
    - File constraints: Each file must be less than 300 lines (refactor if exceeded).

2) **Tech Stack**: Use Python (with C++ where performance-critical), cross-platform compatibility (including headless Docker support).

3) **Project Goal**: Create a framework for using the Monte Carlo method to develop robust and profitable indicators. Based on user-defined metrics, the generator should create an indicator that 100% matches these targets.

4) **Monte Carlo Functionality**: Implement comprehensive features:
    - Shuffling, noise injection, Sensitivity Analysis (varying parameters by ±10%), data downloading, etc.
    - Ensure it is fully functional and add any missing essential features.

5) **Performance & Reliability**: All processes must be extremely fast and error-free.

6) **Workflows**:
    - Data Acquisition: Download data from Binance (configurable parameters) in Parquet format (faster than CSV).
    - Sample Generation: Create samples for shuffling and other MC methods.
    - Metrics Definition: Set initial targets (e.g., Profit Factor > 2). Supplement with other essential analysis metrics.
    - Generation Process: User initiates generation with parameters (e.g., 100,000 iterations, selecting specific MC methods).
    - Tool Execution: The tool generates an indicator that passes all robustness and profitability tests. Displays estimated time remaining and a progress bar. Generation happens without visualization for maximum speed.
    - Result Visualization: Upon finding a valid indicator, ask the user to view it on a chart. If accepted, generate a chart with all input parameters, entry/exit points (SL/TP), profit/loss metrics, and validation that it meets all targets.
    - Interactive Mode: Show key checks and internal logic in real-time.

7) **Interface**: Develop a CLI similar to "cline cli" or "anthropic claude code cli" with keyboard navigation (arrow keys and enter) for a superior user experience.

8) **Overfitting Protection**: Prioritize protection against overfitting using all available methods, including rolling walk-forward analysis.

9) **Core Metrics**: Initial metrics configurable via the CLI menu:
    - **Winrate**: Minimally acceptable 40-60%, depending on Risk-Reward ratio (RR). Expectancy formula: `(Winrate × Avg Win) - ((1 - Winrate) × Avg Loss) > 0`.
    - **Profit Factor**: Gross Profit / Gross Loss > 1.5 (ideally > 2).
    - **Sharpe Ratio**: (Return - Risk-free rate) / Volatility > 1 (ideally > 2).
    - **Sortino Ratio**: Similar to Sharpe, but focusing on downside volatility > 1.5.
    - **Max Drawdown**: < 20-30% of capital.
    - **Recovery Factor**: Net Profit / Max Drawdown > 2.
    - **Calmar Ratio**: Annual Return / Max Drawdown > 0.5.

10) **Professional Execution**: Focus on the indicator generator core and its validation methods as the project's heart.

11) **Planning**: Create a detailed plan and conduct brainstorming sessions.

12) **Git Integration**: Private NeoZorK gitserver only (`NeoZorK/Monte-Neo.git`). Not on GitHub.

13) **Version Control & Organization**:
    - Initialize git and set version to `v0.0.4`.
    - Organize files properly (e.g., `docker/` for Docker files, `docs/` for documentation).
    - Only essential files in the root directory.
    - Version number should be manageable from a single location.
    - Always update `INDEX.md` with every file change.
