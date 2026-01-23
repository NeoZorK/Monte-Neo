# ROADMAP.md - Development Roadmap

## Version 0.0.1 - Initial Alpha (Current)

- [x] Project architecture and folder structure
- [x] Basic OHLCV downloader for Binance
- [x] Initial Monte Carlo Engine (Shuffling, Noise)
- [x] Basic Metrics (Profit Factor, Winrate)
- [x] Interactive CLI Menu

## Version 0.0.2 - Robustness Core

- [x] Sensitivity analysis (Parameter ±10%)
- [x] Walk-forward analysis
- [x] Numba-accelerated metrics
- [x] Unit and integration test suite (uv + pytest)
- [x] Dockerization and docker-compose

## Version 0.0.3 - Visualization & UX

- [x] Interactive terminal candlestick charts
- [x] Trade list visualization (Rich tables)
- [ ] Multi-thread optimization for UI
- [ ] User-defined custom indicator templates

## Version 0.0.4 - Advanced Analytics

- [ ] Correlation analysis between indicators
- [ ] Regime detection (Trend vs Range)
- [ ] Machine learning integration for candidate selection

## Version 1.0.0 - Full Release

- [ ] C++ accelerated core for 1M+ iterations
- [ ] Real-time data streaming (WebSockets)
- [ ] Cloud deployment templates (AWS/GCP)

---

## Milestones

| Version | Target | Status |
|---------|--------|--------|
| v0.0.1 | Initial Alpha Setup | ✅ |
| v0.0.2 | Robustness Core & Tests | ✅ |
| v0.0.3 | Visualization & UX | 🔄 |
| v0.0.4 | Advanced Analytics | 📅 |
| v1.0.0 | Full Release | 📅 |
