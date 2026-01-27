# 🗺️ Monte-Neo Roadmap (v0.0.5)

## Version 0.0.3 - Completed (Performance, Workflows & Trust)

- [x] **GPU/Metal Acceleration**: Initial implementation using MLX (Apple Silicon).
- [x] **Benchmark Suite**: Verified high-throughput throughput.
- [x] **Sequential "Wizard" Mode**: Interactive step-by-step Monte Carlo validation.
- [x] **Discovery Proof**: Enhanced visualization and robustness certificates.

## Version 0.0.4 - Extreme Performance & Metal Core (Completed)

### 1. Hardware-Level Optimization
- [x] **Float8 Precision Support**: Implement float8 (E4M3/E5M2) support for massive memory bandwidth savings and increased throughput during Monte Carlo simulations.
- [x] **Direct Metal Shaders (C++)**: Move core simulation kernels from MLX to custom Metal Shaders (C++) for maximum control over Apple Silicon hardware.
- [x] **Optimized Memory Access**: Implement tiling and memory coalescing in C++/Metal kernels.
- [x] **Hardware Verification Suite**: Dedicated `verify_hardware.py` script to validate Float8 and Metal integration.

### 2. Production Readiness & Logic
- [x] **Advanced Sequential Logic**: Fix and improve Sequential MC flow to ensure all tests are passed sequentially with hard gates.
- [x] **Production Readiness Scoring**: Implement a "Production Score" based on MC survivability, walk-forward efficiency, and parameter stability.
- [x] **Actionable Production Advice**: Detailed reports on what exactly needs to be improved for an indicator to be "Production Ready" (e.g., "Increase stop-loss distance to survive noise tests").

### 3. Settings & Configuration
- [x] **Hardware Toggle Menu**: Add CLI settings to toggle between CPU (Numba), GPU (MLX), and Extreme GPU (Metal C++).
- [x] **Precision Selection**: Menu option to choose between float32, float16, and float8 execution modes.

## Version 0.0.5 - Advanced Analytics & Intelligence (Current)

- [ ] **Correlation Analysis**: Detect and eliminate redundant indicator signals.
- [ ] **Regime Detection**: Automatic detection of Trend vs Range markets.
- [ ] **ML Candidate Selection**: Use light gradient boosting or simple neural nets to pre-screen indicator candidates before MC testing.

## Version 0.0.6 - Cloud & Scale

- [ ] **Real-time Data Streaming**: WebSockets integration for live validation.
- [ ] **Distributed MC**: Run Monte Carlo across multiple machines/containers.
- [ ] **Cloud Deployment**: AWS/GCP templates for high-performance scaling.

---

## Milestones

| Version | Target | Status |
|---------|--------|--------|
| v0.0.1 | Initial Alpha Setup | ✅ |
| v0.0.2 | Robustness Core & Tests | ✅ |
| v0.0.3 | Performance & Workflows | ✅ |
| v0.0.4 | Extreme Performance & Metal | ✅ |
| v0.0.5 | Advanced Analytics | 🏗️ |
| v0.0.6 | Cloud & Scale | 📅 |
