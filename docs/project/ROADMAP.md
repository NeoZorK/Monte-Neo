# 🗺️ Monte-Neo Roadmap (v0.0.3)

## Version 0.0.2 - Completed

- [x] Project architecture and folder structure
- [x] Basic OHLCV downloader for Binance
- [x] Initial Monte Carlo Engine (Shuffling, Noise)
- [x] Basic Metrics (Profit Factor, Winrate)
- [x] Interactive CLI Menu
- [x] Sensitivity analysis (Parameter ±10%)
- [x] Walk-forward analysis
- [x] Numba & C++ accelerated metrics
- [x] Unit and integration test suite (uv + pytest)
- [x] Dockerization and docker-compose

## Version 0.0.3 - Current (Performance, Workflows & Trust)

### 1. High-Performance Core (>300k ops/sec)
- [x] **GPU/Metal Acceleration**: Implement `gpu_core` using MLX (Apple Silicon) or Metal Shaders for massive parallelization of Monte Carlo simulations.
- [ ] **C++ Integration**: Optional C++ bindings for critical bottlenecks if Python/Numba is insufficient.
- [x] **Benchmark Suite**: Achieve and verify >300,000 operations/sec throughput (Achieved ~780k/sec).

### 2. Sequential "Wizard" Mode
- [x] **Interactive Step-by-Step**: "Sequential Indicator Generator" mode where MC methods run one by one.
- [x] **Detailed Feedback Loop**: After each MC step (e.g., Shuffling), pause and show:
    - Exact pass rate (e.g., "Survived 950/1000 shuffles").
    - Interpretation (e.g., "Strategy is robust against trend removal").
    - Actionable advice for the next step.

### 3. "Trust the System" Visualization
- [x] **Discovery Proof**: Explicitly demonstrate the *search* and *validation* process. Show that the final indicator is a "survivor" of rigorous stress testing.
- [x] **Robustness Certificate**: Final report explaining *why* the indicator is production-ready (e.g., "Profitability maintained across 5 market regimes").

### 4. Custom Strategy Lab ("Bring Your Own Formula")
- [x] **Custom Formula Menu**: New menu option "🧪 Test Custom Formula".
- [x] **Template System**: Provide `user_indicators/template.py` with working examples for users to plug in their logic.
- [x] **Full Diagnostic Suite**:
    - Run user's formula against all enabled Monte Carlo methods.
    - Check for Overfitting (Training vs Test divergence).
    - Check for Robustness (Noise/Parameter sensitivity).
- [x] **Educational Report**: Generate a detailed "Health Check" for the user's formula:
    - "Good": Stable parameters, high win rate.
    - "Needs Work": Fails walk-forward, high drawdown in noise tests.
    - Explanation of each MC method used on *their* specific formula.

## Version 0.0.4 - Advanced Analytics

- [ ] Correlation analysis between indicators
- [ ] Regime detection (Trend vs Range)
- [ ] Machine learning integration for candidate selection

## Version 0.0.5 - High Performance & Cloud

- [ ] Real-time data streaming (WebSockets)
- [ ] Cloud deployment templates (AWS/GCP)

---

## Milestones

| Version | Target | Status |
|---------|--------|--------|
| v0.0.1 | Initial Alpha Setup | ✅ |
| v0.0.2 | Robustness Core & Tests | ✅ |
| v0.0.3 | Performance & Workflows | 🔄 |
| v0.0.4 | Advanced Analytics | 📅 |
| v0.0.5 | High Performance & Cloud | 📅 |
