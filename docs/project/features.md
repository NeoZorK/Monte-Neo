# Features

## Core Features

- **Indicator Generation**: Automatic search for profitable trading indicators.
- **Monte Carlo Robustness**:
  - **Return Shuffling**: Tests if profit is dependent on sequence.
  - **Noise Injection**: Simulates market volatility and slippage.
  - **Sensitivity Analysis**: Varies parameters by ±10% to ensure stability.
  - **Walk-Forward Analysis**: Realistic out-of-sample validation.
- **Data Management**:
  - Fast Parquet-based storage.
  - One-click Binance data downloader.
- **Interactive CLI**:
  - Arrow-key navigation for all configurations.
  - Real-time progress bars with ETA.
  - Interactive candlestick charts directly in the terminal.
- **Automated Verification**:
  - Full test suite for algorithms and UI.
  - Memory and CPU stress testing.
- **Deployment**:
  - Dockerized environment for reproducible results.
  - Headless mode for server-side generation.
- **Professional Metrics**:
  - Sharpe, Sortino, Calmar ratios.
  - Max Drawdown with duration analysis.
  - Expectancy and Recovery factor.
  - Parallelized calculation for high efficiency.
