# Pre-registration: confirmatory calibration of the Alpha Readiness Level

Author: Rostyslav Shcherbyna (ORCID 0009-0000-3773-5789). Written on 2026-11-27, before the confirmatory run.

This document, the code and `SHA256SUMS` are published as a Zenodo record before the first confirmatory case is run;
the publication time stamp of that record is the evidence of the order. The launcher records the DOI, the start time
and the hash of `SHA256SUMS`.

## Question

The rules of the Alpha Readiness Level (ARL) were chosen on 350,000 development cases (base seed 20261119). The rates
measured on those cases are in-sample. Do they hold on new cases, and how large is false promotion when traps receive
the same evidence artefacts as honest cases?

## What is frozen

- Code and rules: Monte-Neo tag `v0.57.0`, commit `cd88c80066df9baf658e39aeeb5d753c979c9f09`, unchanged; dependencies
  as locked in that tag; Python 3.13.16.
- Generator `calib.py`, analysis `analyze.py`, launcher `run.sh`: the files deposited with this document (hashes in
  `SHA256SUMS`).
- Real daily bars: the file with SHA-256 `de57183c5361ea7e68e0dd195712e1780f3f2e41867a74eed98723aa94c6f348`
  (152 series, listed in `bars_manifest.csv`). The bars are the same as in development; only the sampled windows and the
  noise signals are new. Real-data noise cases therefore reuse the development series (long windows overlap strongly):
  for them the run tests new windows and signals, not new markets.
- Base seed of the confirmatory run: `20261128`. No case with this seed was run or inspected before this document was
  written.
- 350,000 cases with the development schedule of groups and cells.

## Differences from the development design

1. New base seed.
2. Cross-sectional trap and twin data use the full case seed (development used the seed modulo 1,000, which repeated
   data sets). The seed of the placebo permutations stays the case seed modulo 1,000, as in development.
3. Two arms on the same seeds:
   - **parity** (primary): every case receives a fresh trial ledger, including the hidden-trials trap, and every
     cross-sectional case that declares no membership file receives a fixed-universe one. For a trap this models a user
     who supplies the cheapest declaration that the rules accept.
   - **silent** (replication of the development design): the hidden-trials trap keeps no ledger and cross-sectional
     traps receive no added membership file. Only the cases whose inputs differ are run again; all other results are
     shared with the parity arm.

   The returns-only phantom-pairs trap takes neither artefact in either arm.

## Measures

False promotion: the share of trap (A) or noise (B) cases whose level exceeds the maximum fixed by design. Power: the
share of planted-edge (C) cases that reach a level. Intervals: Wilson 95 %.

## Pilot disclosure

Before this document was written, 1,500 cases with the separate base seed 20261127 were run in both arms to test the
software. Their parity-arm results were seen: 15 of 40 hidden-trials cases reached level 4, and some cross-sectional
traps were promoted. Earlier, 40 development hidden-trials cases rerun with an empty ledger gave 18 of 40. Predictions
P2 and P3 are informed by these observations.

## Predictions

All bounds in P1-P3 apply to the point estimate; Wilson intervals are reported but are not used to decide whether a
prediction is met.

**P1, replication (silent arm).** Each of the following lies within 1.0 percentage point of its development value under
the final rules:

| measure | development value |
|---|---|
| False promotion, A | 0.74 % |
| False promotion, B | 0.77 % |
| B on real market bars | 1.73 % |
| Regime-decay trap above its maximum (within 1.5 points) | 6.96 % |
| Planted single-asset edge, level 3 or above | 57.94 % |
| Planted single-asset edge, level 6 or above | 28.94 % |
| Planted cross-sectional edge E1-E4, level 3 or above | 79.62 % |
| Planted cross-sectional edge E1-E4, level 6 or above | 52.78 % |

The hidden-trials trap reaches level 4 or above in no case (this holds by construction and is a software check).

**P2, parity arm, hidden trials.** The hidden-trials trap reaches level 4 or above in 25 % to 55 % of cases.

**P3, parity arm, all traps.** Pooled false promotion of population A lies between 4 % and 14 %.

**P4, software check.** The first 3,500 cases are run again in full in the silent configuration (`silent_check`).
Every case whose inputs do not differ between the arms has the same level, depth, blocking level, blocking rule and
caps as in the parity arm, and every asymmetric case (hidden-trials trap, cross-sectional traps) matches the silent
arm. In the silent arm of the report, cases whose inputs do not differ are taken from the parity run.

## Reporting

All predictions are reported as met or not met, with the numbers produced by `analyze.py`, including the table of false
promotion by trap type. Rules, thresholds, case definitions and truth maxima are not changed after the run starts. A
case that fails with a software error is retried once with the same seed; cases that still fail are counted and
reported. Any other departure from this document is listed in the paper.
