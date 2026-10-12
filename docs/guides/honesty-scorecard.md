# Honesty scorecard

Generated from the hypothesis zoo (level `lite`). A *leak* counts as caught when the truncation or perturbation probe fails it;
an *honest* strategy counts as correct when no accusing check fails it. Intervals are Wilson 95 %.

| Class | Correct | Cases | Rate | 95 % interval |
|---|---|---|---|---|
| Honest: arrays | 8 | 8 | 100.0% | 67.6% – 100.0% |
| Honest: indicators | 5 | 5 | 100.0% | 56.6% – 100.0% |
| Honest: lookalike | 6 | 6 | 100.0% | 61.0% – 100.0% |
| Honest: time | 9 | 9 | 100.0% | 70.1% – 100.0% |
| Honest: wholesample | 7 | 7 | 100.0% | 64.6% – 100.0% |
| Honest: windows | 35 | 35 | 100.0% | 90.1% – 100.0% |
| Leak: arrays | 20 | 20 | 100.0% | 83.9% – 100.0% |
| Leak: fits | 6 | 6 | 100.0% | 61.0% – 100.0% |
| Leak: indicators | 6 | 6 | 100.0% | 61.0% – 100.0% |
| Leak: labels | 6 | 6 | 100.0% | 61.0% – 100.0% |
| Leak: pit | 2 | 2 | 100.0% | 34.2% – 100.0% |
| Leak: time | 14 | 14 | 100.0% | 78.5% – 100.0% |
| Leak: wholesample | 23 | 23 | 100.0% | 85.7% – 100.0% |
| Leak: windows | 24 | 24 | 100.0% | 86.2% – 100.0% |

## The other classes

| Class | Passing | Cases |
|---|---|---|
| A10 universes | 17 | 17 |
| A11 machine learning | 14 | 14 |
| A12 quotes | 10 | 10 |
| A13 engine fuzzing | 361 | 361 |
| A14 repainting (history and forming bar) | 27 | 27 |
| A15 alpha (traps and honest twins) | 29 | 29 |
| A16 repair never reports REPAIRED on a leaking trap | 6 | 6 |
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
