# Example reports

Six real reports, each from a verification run on synthetic data where the truth is known. Open
one to see what a verdict looks like: the one-sentence reason, the category cards, the charts,
the evidence and the checks. Every report is one self-contained HTML file: no scripts, no
network, and it prints to PDF from the browser.

| Report | What it shows | Verdict |
|--------|---------------|---------|
| [A leak](assets/reports/leak.html) | A strategy that reads the next close (`shift(-1)`). The report names the line and the bars where the signal changes when the future is removed | REJECT |
| [No edge](assets/reports/no-edge.html) | A moving-average crossover on a random walk: it loses money after costs and does not survive the number of variants tried | REJECT |
| [An honest strategy](assets/reports/honest.html) | Momentum on data with a planted edge: beats its 200 time-shifted copies, survives costs, and shows that one bar of execution delay removes the profit | PASS WITH WARNINGS |
| [A parameter search](assets/reports/grid.html) | A grid over `lookback` with walk-forward validation and a parameter heat map | PASS WITH WARNINGS |
| [A universe](assets/reports/universe.html) | Cross-sectional momentum on several symbols, with the survivorship check | REJECT |
| [Bad ticks](assets/reports/bad-ticks.html) | Honest code whose profit is one-bar price spikes: the data, not the strategy, makes the money | REJECT |

## How to read a report

- **The line under the title** says why the verdict is what it is.
- **The four cards** count the checks per family: integrity, look-ahead, economics, statistics.
- **Equity** is on a log scale next to buy and hold, with the drawdown underneath.
- **The timing test** shows the net return of 200 time-shifted copies of the same positions. A real
  signal beats most of them; a strategy that only holds a rising market does not.
- **Sensitivity to costs** shows how fast the profit disappears as trading costs grow, and where the
  modeled cost sits.
- **Evidence** lists the bars where a signal changed when the future was removed, and the source
  lines the linter flagged.

The reports are regenerated with `uv run python scripts/make_report_gallery.py`. Make your own:

```bash
monte-neo verify --ohlcv prices.csv --strategy my_strategy.py --html report.html
```
