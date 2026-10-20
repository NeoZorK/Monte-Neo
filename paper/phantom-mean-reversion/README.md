# Phantom Mean Reversion: preprint sources

Sources of the preprint "Phantom Mean Reversion: How Rolling Hedge Ratios Manufacture Profits in Pairs-Trading
Backtests" (Rostyslav Shcherbyna, Zaporizhzhia, Ukraine).

| File | What |
|------|------|
| `main.tex` | The manuscript (LaTeX, bibliography inside) |
| `figures/` | Figures (PDF for the paper, PNG to look at) |
| `code/phantom_mr_sim.py` | Reproduces Table 1 (numpy only) |
| `code/mechanism_check.py` | Reproduces the two numbers of the mechanism paragraph (Section 2) |
| `code/other_hedges.py` | Reproduces Table 2: EWMA and Kalman hedges, a cointegrated pair (numpy only) |
| `code/make_figures.py` | Reproduces the figures (numpy and matplotlib) |
| `results.json`, `results_other.json` | The numbers of the two tables (seed 20261015) |
| `build_arxiv.sh` | Builds the arXiv upload archive |

```bash
python3 code/phantom_mr_sim.py --out results.json            # Table 1
python3 code/other_hedges.py --out results_other.json        # Table 2
python3 code/make_figures.py results.json figures/           # Figures
./build_arxiv.sh                                             # build/phantom-mean-reversion-arxiv.tar.gz
```

The checks the paper describes are in Monte-Neo: `monte-neo verify --legs`, `monte-neo verify --null-test` and
`monte-neo verify --demo-phantom` (see `docs/guides/phantom-profit.md`).

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict
future returns.
