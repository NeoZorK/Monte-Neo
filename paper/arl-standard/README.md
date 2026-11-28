# The Alpha Readiness Level: paper sources and calibration code

Sources of the paper "The Alpha Readiness Level: A Calibrated Evidence Scale for Trading-Strategy Backtests"
(Rostyslav Shcherbyna, Zaporizhzhia, Ukraine). The Alpha Readiness Level (ARL) is a nine-level scale that states how
far the evidence behind a backtest has been taken. It is an open proposal, not an industry standard, and not investment
advice.

Pre-registration of the confirmatory run: [doi:10.5281/zenodo.24603671](https://doi.org/10.5281/zenodo.24603671).
Per-case results are deposited as a later version of the same record
([all versions](https://doi.org/10.5281/zenodo.24603670)).

| File | What |
|------|------|
| `main.tex` | The manuscript (LaTeX, bibliography inside) |
| `examples/arl_examples.py` | The five worked examples of the paper, with their output |
| `code/calib.py` | Generator and runner of the calibration cases |
| `code/analyze.py` | Computes the calibration numbers from per-case results |
| `code/run.sh` | Clones the verifier at the frozen tag, installs the locked environment, runs and resumes |
| `code/shrink_results.py` | Makes the compact per-case tables of the results archive |
| `code/PREREGISTRATION.md` | Plan and predictions, written before the confirmatory run |
| `code/bars_manifest.csv` | The 152 real daily series: source, symbol, class, dates, rows, hash (bars not redistributed) |
| `code/numbers_development.md`, `code/numbers_confirmatory.md` | Output of `analyze.py` |
| `code/SHA256SUMS` | Hashes of the files in `code/` |

## Worked examples (seconds)

With Monte-Neo 0.57.0 installed (`pip install monte-neo==0.57.0`):

```bash
python examples/arl_examples.py
```

## Recompute the numbers of the paper (minutes)

Download the results archive from Zenodo, unpack it and, inside the unpacked folder, run the commands of its
`README.md`. Needs Python with numpy, pandas and pyarrow.

## Rerun the calibration (hours)

Needs git, uv, bash and screen, about 12 GB of disk and about 12 hours on an Apple M1 Pro with 8 processes. The 7 % of
cases that use real bars need your own copy of the bars (`ARL_BARS`); see `code/bars_manifest.csv`.

```bash
cd code
./run.sh setup
./run.sh replicate
```

## Build the PDF

```bash
tectonic main.tex
```
