# Honesty scorecard

Generated from the hypothesis zoo (level `full`). A *leak* counts as caught when the truncation or perturbation probe fails it;
an *honest* strategy counts as correct when no accusing check fails it. Intervals are Wilson 95 %.

| Class | Correct | Cases | Rate | 95 % interval |
|---|---|---|---|---|
| Honest: arrays | 48 | 48 | 100.0% | 92.6% – 100.0% |
| Honest: indicators | 30 | 30 | 100.0% | 88.6% – 100.0% |
| Honest: lookalike | 36 | 36 | 100.0% | 90.4% – 100.0% |
| Honest: time | 54 | 54 | 100.0% | 93.4% – 100.0% |
| Honest: wholesample | 42 | 42 | 100.0% | 91.6% – 100.0% |
| Honest: windows | 210 | 210 | 100.0% | 98.2% – 100.0% |
| Leak: arrays | 120 | 120 | 100.0% | 96.9% – 100.0% |
| Leak: fits | 36 | 36 | 100.0% | 90.4% – 100.0% |
| Leak: indicators | 36 | 36 | 100.0% | 90.4% – 100.0% |
| Leak: labels | 36 | 36 | 100.0% | 90.4% – 100.0% |
| Leak: pit | 12 | 12 | 100.0% | 75.7% – 100.0% |
| Leak: time | 84 | 84 | 100.0% | 95.6% – 100.0% |
| Leak: wholesample | 138 | 138 | 100.0% | 97.3% – 100.0% |
| Leak: windows | 144 | 144 | 100.0% | 97.4% – 100.0% |

## The other classes

| Class | Passing | Cases |
|---|---|---|
| A10 universes | 17 | 17 |
| A11 machine learning | 14 | 14 |
| A12 quotes | 10 | 10 |
| A13 engine fuzzing | 361 | 361 |
| A14 repainting (history and forming bar) | 27 | 27 |
| A4 data defects (21 x 3 frequencies) | 75 | 75 |
| A5 execution and economics | 21 | 21 |
| A6 statistics and method | 18 | 18 |
| A7 claims | 13 | 13 |
| A9 metamorphic relations | 36 | 36 |
| labels checked by the independent oracle | 172 | 172 |
| suggest_fix | 114 | 114 |

## How to read this

The mechanisms were written by the maintainers and the labels were checked by an oracle that does not use the verifier, so a rate of 100 %
is a regression guard on known mechanisms, not a claim about leaks nobody thought of. It does not measure: real Freqtrade and Lean runs
(the adapters are tested on fake data), open-source strategies in the wild, or a model fitted when the module loads that still reacts to its input.

## Known gaps

Cases the verifier gets wrong today. They are tracked in `tests/zoo/known_gaps.json`; a new miss fails CI.

- none
