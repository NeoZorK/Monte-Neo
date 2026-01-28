# 🗺️ Monte-Neo Roadmap (v0.0.6)

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

### 🚀 Phase 6: v0.0.6 - Global Leadership & Production Mastery (Completed)
- [x] **Smart Portfolio Engine**: Multi-indicator management with Kelly Criterion.
- [x] **Non-Repainting Validator**: Hard enforcement of signal causality.
- [x] **Advanced Noise Suite**: Latency shifts, variable spreads, and slippage.
- [x] **Combinatorial WFO (CSCV)**: Advanced overfitting detection (PBO).
- [x] **One-Click Production Export**: C++/Metal binary standalone generation.
- [x] **AI-Driven Evolution**: Self-correcting indicator formulas.
- [x] **Global Leadership Pipeline**: End-to-end automated discovery workflow.
- [x] **Realistic Calculation Engine**: $100,000 initial deposit & 1.0 leverage hard-enforcement.
- [x] **High Test Coverage**: Core modules (Backtesting, Metrics, Monte Carlo) achieved ~100% coverage.
- [x] **Unified UI/UX**: Streamlined progress bars and logs for clear workflow execution.

### 🌟 Phase 7: v0.0.7 - Ecosystem & Scaling (Planned)
- [ ] **Web-based Dashboard**: Real-time monitoring and strategy management.
- [ ] **Multi-Exchange Support**: Bybit, OKX, and Kraken integration.
- [ ] **Cloud-Native Workers**: Distributed Monte Carlo simulations via Kubernetes.
- [ ] **Advanced ML Integration**: Transformer-based signal refinement.

---

## ⏱️ 6-Hour Sprint Plan (Completed)

### Hour 1-2: Production Export & C++ Core
- [x] Implement `ProductionExporter` for zero-latency standalone execution.
- [x] Create C++ templates for indicator logic (fast-path).
- [x] Add `uv run monte-neo export` command.

### Hour 3-4: AI-Driven Evolution (Symbolic Regression)
- [x] Implement Genetic Programming (GP) for formula discovery.
- [x] Add "Smart Mutation" based on performance feedback loops.
- [x] Integrate AI-inspired heuristics for formula optimization.

### Hour 5: Portfolio Intelligence & Risk
- [x] Implement multi-asset correlation clustering.
- [x] Automated portfolio rebalancing logic (Risk Parity/Kelly).
- [x] Dashboard for "Portfolio Robustness" (Combined MC).

### Hour 6: Certification & Final Integration
- [x] Auto-generate "World-Class Robustness Certificate".
- [x] Full pipeline verification (Data -> Evolution -> Validation -> Export).
- [x] UI/UX final touch for the "Wizard" mode (Global Leadership Pipeline).

---

## Milestones

