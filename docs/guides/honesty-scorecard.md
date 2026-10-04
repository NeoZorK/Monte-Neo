# Honesty scorecard

Generated from the hypothesis zoo (level `lite`). A *leak* counts as caught when the truncation or perturbation probe fails it;
an *honest* strategy counts as correct when no accusing check fails it. Intervals are Wilson 95 %.

| Class | Correct | Cases | Rate | 95 % interval |
|---|---|---|---|---|
| Honest: arrays | 7 | 8 | 87.5% | 52.9% – 97.8% |
| Honest: indicators | 5 | 5 | 100.0% | 56.6% – 100.0% |
| Honest: lookalike | 4 | 6 | 66.7% | 30.0% – 90.3% |
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

## Known gaps

Cases the verifier gets wrong today. They are tracked in `tests/zoo/known_gaps.json`; a new miss fails CI.

- `hl_label_shifted_back/direct`: static lint fails shift(-1) even when the label is shifted back before use
- `hl_label_shifted_back/helper`: static lint fails shift(-1) even when the label is shifted back before use
- `hl_label_shifted_back/lambda`: static lint fails shift(-1) even when the label is shifted back before use
- `hl_label_shifted_back/method`: static lint fails shift(-1) even when the label is shifted back before use
- `hl_label_shifted_back/pipe`: static lint fails shift(-1) even when the label is shifted back before use
- `hl_label_unused/direct`: static lint fails shift(-1) even when the shifted label never reaches the signal
- `hl_label_unused/helper`: static lint fails shift(-1) even when the shifted label never reaches the signal
- `hl_label_unused/lambda`: static lint fails shift(-1) even when the shifted label never reaches the signal
- `hl_label_unused/method`: static lint fails shift(-1) even when the shifted label never reaches the signal
- `hl_label_unused/pipe`: static lint fails shift(-1) even when the shifted label never reaches the signal
- `hn_uniform_filter_causal/direct`: static lint fails scipy uniform_filter1d by name; it cannot see origin= makes the window causal
- `hn_uniform_filter_causal/helper`: static lint fails scipy uniform_filter1d by name; it cannot see origin= makes the window causal
- `hn_uniform_filter_causal/lambda`: static lint fails scipy uniform_filter1d by name; it cannot see origin= makes the window causal
- `hn_uniform_filter_causal/method`: static lint fails scipy uniform_filter1d by name; it cannot see origin= makes the window causal
- `hn_uniform_filter_causal/pipe`: static lint fails scipy uniform_filter1d by name; it cannot see origin= makes the window causal
