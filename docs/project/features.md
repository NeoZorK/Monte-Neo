# Features

## Core Features

- **Indicator Generation**: Automatic search for profitable trading indicators.
- **Dynamic Indicator Generation**:
  - Generates novel indicators using genetic programming concepts.
  - Creates random valid Python formulas from market data.
  - **Evolutionary Optimization**: Cross-breeds and mutates the best candidates to evolve superior strategies.
- **Monte Carlo Robustness**:
  - **Return Shuffling**: Tests if profit is dependent on sequence.
  - **Noise Injection**: Simulates market volatility and slippage.
  - **Sensitivity Analysis**: Varies parameters by ±10% to ensure stability.
  - **Walk-Forward Analysis**: Realistic out-of-sample validation.
  - **Block Bootstrap**: Resamples contiguous blocks to preserve market structure.
  - **Sequential Validation Mode**: Runs methods one-by-one with early termination to save time.
  - **Dynamic Pass Threshold**: Configurable success criteria (e.g., 95% pass rate required).
- **Data Management**:
  - Fast Parquet-based storage.
  - One-click Binance data downloader.
- **Interactive CLI**:
  - Arrow-key navigation for all configurations.
  - Real-time progress bars with ETA.
  - **Terminal Charts**: High-resolution candlestick charts directly in the console.
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
  - **Risk Management**:
    - Built-in Stop Loss (SL) and Take Profit (TP) support.
    - Configuration via Risk Ratio (e.g., 2:1, 3:1).
    - Configurable presets (Conservative, Standard, Aggressive).
  - Parallelized calculation for high efficiency.
