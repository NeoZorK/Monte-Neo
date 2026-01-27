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

### ✅ Phase 5: v0.0.5 - Robustness Factory (Current)
- [x] **C++/Metal Engine**: Lightning-fast GPU backtesting extension.
- [x] **Unified Kernel Architecture**: Zero-latency trade execution on GPU.
- [x] **GPU Grid Search**: Testing thousands of scenarios in milliseconds.
- [x] **Walk-Forward Optimization**: Hardware-accelerated validation.
- [x] **Production Gate**: Robustness scoring and certification.

### 🚀 Phase 6: v0.0.6 - Global Leadership & Production Mastery (Current)
- [x] **Smart Portfolio Engine**: Multi-indicator management with Kelly Criterion.
- [x] **Non-Repainting Validator**: Hard enforcement of signal causality.
- [x] **Advanced Noise Suite**: Latency shifts, variable spreads, and slippage.
- [x] **Combinatorial WFO (CSCV)**: Advanced overfitting detection (PBO).
- [ ] **One-Click Production Export**: C++/Metal binary standalone generation.
- [ ] **AI-Driven Evolution**: Self-correcting indicator formulas.

### 📅 Phase 7: v0.0.7 - Cloud & Scale
- [ ] **Distributed GPU Cloud**: Running simulations across multiple nodes.
- [ ] **Real-time Monitoring**: Dashboard for production performance tracking.

