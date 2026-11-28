# ARL calibration numbers

## parity
cases expected 350,000, present 350,000, missing 0
cases: 350,000 (A 84,000, B 77,000, C 189,000); distinct (kind, seed): 349,994

### Headline
| measure | value |
|---|---|
| False promotion, A (traps) | 8.29 % [8.10, 8.48] (6,962/84,000) |
| False promotion, B (noise) | 0.82 % [0.76, 0.89] (634/77,000) |
| B on random walks and noise scores | 0.36 % [0.32, 0.42] (191/52,504) |
| B on real market bars | 1.81 % [1.65, 1.98] (443/24,496) |
| Hidden-trials trap at level 4 or above | 46.87 % [45.83, 47.91] (4,177/8,912) |
| Regime-decay trap above its maximum | 7.52 % [6.99, 8.09] (670/8,904) |
| Cost-omission trap above its maximum | 0.01 % [0.00, 0.06] (1/8,912) |
| Planted single-asset edge, level 3 or above | 58.20 % [57.91, 58.48] (65,179/112,000) |
| Planted single-asset edge, level 4 or above | 46.39 % [46.10, 46.68] (51,956/112,000) |
| Planted single-asset edge, level 5 or above | 32.55 % [32.28, 32.82] (36,455/112,000) |
| Planted single-asset edge, level 6 or above | 29.04 % [28.77, 29.30] (32,520/112,000) |
| Planted cross-sectional edge E1-E4, level 3 or above | 79.68 % [79.34, 80.01] (43,629/54,757) |
| Planted cross-sectional edge E1-E4, level 6 or above | 52.78 % [52.36, 53.19] (28,899/54,757) |

### False promotion by trap type
| trap | max level | above maximum |
|---|---|---|
| cost_omission | 2 | 0.01 % [0.00, 0.06] (1/8,912) |
| global_zscore | 1 | 0.00 % [0.00, 0.09] (0/4,456) |
| hidden_trials | 3 | 46.87 % [45.83, 47.91] (4,177/8,912) |
| lookahead_centered | 1 | 0.00 % [0.00, 0.09] (0/4,456) |
| lookahead_shift | 1 | 0.00 % [0.00, 0.09] (0/4,456) |
| phantom_pairs | 2 | 0.00 % [0.00, 0.09] (0/4,452) |
| regime_decay | 6 | 7.52 % [6.99, 8.09] (670/8,904) |
| survivor_universe | 4 | 0.00 % [0.00, 0.09] (0/4,452) |
| zoo_trap:book_clone | 4 | 11.81 % [10.65, 13.09] (318/2,692) |
| zoo_trap:dies_after_discovery | 4 | 0.78 % [0.51, 1.19] (21/2,692) |
| zoo_trap:exact_values | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:first_day_of_month | 4 | 0.00 % [0.00, 0.14] (0/2,693) |
| zoo_trap:illiquid_shorts | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:inflated_claim | 4 | 22.51 % [20.97, 24.13] (606/2,692) |
| zoo_trap:membership_window | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:noise_score | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:repackaged_momentum | 4 | 0.00 % [0.00, 0.14] (0/2,693) |
| zoo_trap:same_date_new_york | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:short_volatility | 4 | 0.00 % [0.00, 0.14] (0/2,693) |
| zoo_trap:survivor_universe | 4 | 43.42 % [41.56, 45.31] (1,169/2,692) |
| zoo_trap:three_symbols | 4 | 0.00 % [0.00, 0.14] (0/2,693) |

### Honest twins of the cross-sectional traps
| twin | level 6 or above |
|---|---|
| zoo_twin:book_clone | 62.42 % [60.10, 64.68] (1,068/1,711) |
| zoo_twin:dies_after_discovery | 90.59 % [89.11, 91.88] (1,550/1,711) |
| zoo_twin:exact_values | 91.88 % [90.49, 93.08] (1,572/1,711) |
| zoo_twin:first_day_of_month | 75.57 % [73.48, 77.55] (1,293/1,711) |
| zoo_twin:illiquid_shorts | 9.00 % [7.73, 10.45] (154/1,711) |
| zoo_twin:inflated_claim | 10.93 % [9.54, 12.50] (187/1,711) |
| zoo_twin:membership_window | 10.70 % [9.32, 12.25] (183/1,711) |
| zoo_twin:noise_score | 33.78 % [31.58, 36.06] (578/1,711) |
| zoo_twin:repackaged_momentum | 94.39 % [93.20, 95.38] (1,615/1,711) |
| zoo_twin:same_date_new_york | 2.45 % [1.82, 3.30] (42/1,711) |
| zoo_twin:short_volatility | 36.65 % [34.39, 38.96] (627/1,711) |
| zoo_twin:survivor_universe | 13.85 % [12.30, 15.57] (237/1,711) |
| zoo_twin:three_symbols | 96.79 % [95.84, 97.52] (1,656/1,711) |

### Noise by data and K
| data | K | above level 3 |
|---|---|---|
| null_real | 1 | 2.11 % [1.78, 2.50] (129/6,124) |
| null_real | 10 | 2.96 % [2.56, 3.41] (181/6,124) |
| null_real | 100 | 1.37 % [1.11, 1.69] (84/6,124) |
| null_real | 1000 | 0.80 % [0.61, 1.06] (49/6,124) |
| null_scores | 1 | 0.24 % [0.16, 0.36] (22/9,336) |
| null_scores | 10 | 0.02 % [0.01, 0.08] (2/9,332) |
| null_scores | 50 | 0.00 % [0.00, 0.04] (0/9,332) |
| null_sim | 1 | 1.34 % [1.08, 1.66] (82/6,128) |
| null_sim | 10 | 1.01 % [0.79, 1.29] (62/6,128) |
| null_sim | 100 | 0.34 % [0.22, 0.52] (21/6,124) |
| null_sim | 1000 | 0.03 % [0.01, 0.12] (2/6,124) |

### Regime-decay by sample length
| years | above maximum |
|---|---|
| 1 | 1.08 % [0.73, 1.60] (24/2,226) |
| 3 | 3.32 % [2.66, 4.15] (74/2,226) |
| 5 | 6.60 % [5.65, 7.71] (147/2,226) |
| 10 | 19.09 % [17.51, 20.78] (425/2,226) |

### Single-asset power, level 3 or above
| Sharpe | years | rate |
|---|---|---|
| 0.5 | 1 | 30.39 % [29.32, 31.47] (2,127/7,000) |
| 0.5 | 3 | 20.01 % [19.09, 20.97] (1,401/7,000) |
| 0.5 | 5 | 12.77 % [12.01, 13.57] (894/7,000) |
| 0.5 | 10 | 5.91 % [5.39, 6.49] (414/7,000) |
| 1.0 | 1 | 47.90 % [46.73, 49.07] (3,353/7,000) |
| 1.0 | 3 | 47.23 % [46.06, 48.40] (3,306/7,000) |
| 1.0 | 5 | 45.46 % [44.29, 46.63] (3,182/7,000) |
| 1.0 | 10 | 44.59 % [43.42, 45.75] (3,121/7,000) |
| 1.5 | 1 | 64.96 % [63.83, 66.07] (4,547/7,000) |
| 1.5 | 3 | 73.94 % [72.90, 74.96] (5,176/7,000) |
| 1.5 | 5 | 81.76 % [80.84, 82.64] (5,723/7,000) |
| 1.5 | 10 | 89.63 % [88.89, 90.32] (6,274/7,000) |
| 2.0 | 1 | 78.19 % [77.20, 79.14] (5,473/7,000) |
| 2.0 | 3 | 91.94 % [91.28, 92.56] (6,436/7,000) |
| 2.0 | 5 | 96.80 % [96.36, 97.19] (6,776/7,000) |
| 2.0 | 10 | 99.66 % [99.49, 99.77] (6,976/7,000) |

### Single-asset power, level 6 or above
| Sharpe | years | rate |
|---|---|---|
| 0.5 | 1 | 0.34 % [0.23, 0.51] (24/7,000) |
| 0.5 | 3 | 1.36 % [1.11, 1.66] (95/7,000) |
| 0.5 | 5 | 2.01 % [1.71, 2.37] (141/7,000) |
| 0.5 | 10 | 4.23 % [3.78, 4.73] (296/7,000) |
| 1.0 | 1 | 1.49 % [1.23, 1.80] (104/7,000) |
| 1.0 | 3 | 5.84 % [5.32, 6.42] (409/7,000) |
| 1.0 | 5 | 13.96 % [13.17, 14.79] (977/7,000) |
| 1.0 | 10 | 38.00 % [36.87, 39.14] (2,660/7,000) |
| 1.5 | 1 | 4.13 % [3.69, 4.62] (289/7,000) |
| 1.5 | 3 | 20.56 % [19.63, 21.52] (1,439/7,000) |
| 1.5 | 5 | 48.33 % [47.16, 49.50] (3,383/7,000) |
| 1.5 | 10 | 87.04 % [86.24, 87.81] (6,093/7,000) |
| 2.0 | 1 | 8.03 % [7.41, 8.69] (562/7,000) |
| 2.0 | 3 | 47.63 % [46.46, 48.80] (3,334/7,000) |
| 2.0 | 5 | 82.06 % [81.14, 82.94] (5,744/7,000) |
| 2.0 | 10 | 99.57 % [99.39, 99.70] (6,970/7,000) |

### Cross-sectional power by edge
| edge | level 3 or above | level 6 or above |
|---|---|---|
| planted_E1 | 27.81 % [27.07, 28.57] (3,808/13,693) | 0.85 % [0.71, 1.02] (116/13,693) |
| planted_E2 | 91.55 % [91.08, 92.01] (12,532/13,688) | 39.78 % [38.96, 40.60] (5,445/13,688) |
| planted_E3 | 99.42 % [99.28, 99.54] (13,609/13,688) | 79.65 % [78.97, 80.32] (10,903/13,688) |
| planted_E4 | 99.94 % [99.88, 99.97] (13,680/13,688) | 90.85 % [90.35, 91.32] (12,435/13,688) |

### Evidence ceilings
| measure | value |
|---|---|
| Hidden-trials cases capped by missing trial evidence | 0.00 % [0.00, 0.04] (0/8,912) |
| Cross-sectional traps stopped at level 5 by the universe check alone | 0/35,000 |

### Noise on real bars by asset class
| asset class | years | above level 3 |
|---|---|---|
| commodity | all | 1.40 % [0.85, 2.30] (15/1,070) |
| commodity | 1 | 3.19 % [1.69, 5.95] (9/282) |
| commodity | 3 | 0.83 % [0.28, 2.40] (3/363) |
| commodity | 5 | 0.71 % [0.24, 2.05] (3/425) |
| crypto | all | 4.04 % [3.68, 4.44] (413/10,220) |
| crypto | 1 | 4.11 % [3.53, 4.77] (164/3,994) |
| crypto | 3 | 4.07 % [3.45, 4.80] (136/3,339) |
| crypto | 5 | 3.91 % [3.27, 4.68] (113/2,887) |
| fx | all | 0.08 % [0.04, 0.15] (9/11,338) |
| fx | 1 | 0.66 % [0.35, 1.26] (9/1,354) |
| fx | 3 | 0.00 % [0.00, 0.22] (0/1,782) |
| fx | 5 | 0.00 % [0.00, 0.18] (0/2,078) |
| fx | 10 | 0.00 % [0.00, 0.06] (0/6,124) |
| index | all | 0.32 % [0.15, 0.70] (6/1,868) |
| index | 1 | 1.21 % [0.56, 2.62] (6/494) |
| index | 3 | 0.00 % [0.00, 0.60] (0/640) |
| index | 5 | 0.00 % [0.00, 0.52] (0/734) |

## silent
cases expected 350,000, present 350,000, missing 0
asymmetric cases of BASE missing from TOP: 0
cases: 350,000 (A 84,000, B 77,000, C 189,000); distinct (kind, seed): 349,994

### Headline
| measure | value |
|---|---|
| False promotion, A (traps) | 0.80 % [0.74, 0.86] (671/84,000) |
| False promotion, B (noise) | 0.82 % [0.76, 0.89] (634/77,000) |
| B on random walks and noise scores | 0.36 % [0.32, 0.42] (191/52,504) |
| B on real market bars | 1.81 % [1.65, 1.98] (443/24,496) |
| Hidden-trials trap at level 4 or above | 0.00 % [0.00, 0.04] (0/8,912) |
| Regime-decay trap above its maximum | 7.52 % [6.99, 8.09] (670/8,904) |
| Cost-omission trap above its maximum | 0.01 % [0.00, 0.06] (1/8,912) |
| Planted single-asset edge, level 3 or above | 58.20 % [57.91, 58.48] (65,179/112,000) |
| Planted single-asset edge, level 4 or above | 46.39 % [46.10, 46.68] (51,956/112,000) |
| Planted single-asset edge, level 5 or above | 32.55 % [32.28, 32.82] (36,455/112,000) |
| Planted single-asset edge, level 6 or above | 29.04 % [28.77, 29.30] (32,520/112,000) |
| Planted cross-sectional edge E1-E4, level 3 or above | 79.68 % [79.34, 80.01] (43,629/54,757) |
| Planted cross-sectional edge E1-E4, level 6 or above | 52.78 % [52.36, 53.19] (28,899/54,757) |

### False promotion by trap type
| trap | max level | above maximum |
|---|---|---|
| cost_omission | 2 | 0.01 % [0.00, 0.06] (1/8,912) |
| global_zscore | 1 | 0.00 % [0.00, 0.09] (0/4,456) |
| hidden_trials | 3 | 0.00 % [0.00, 0.04] (0/8,912) |
| lookahead_centered | 1 | 0.00 % [0.00, 0.09] (0/4,456) |
| lookahead_shift | 1 | 0.00 % [0.00, 0.09] (0/4,456) |
| phantom_pairs | 2 | 0.00 % [0.00, 0.09] (0/4,452) |
| regime_decay | 6 | 7.52 % [6.99, 8.09] (670/8,904) |
| survivor_universe | 4 | 0.00 % [0.00, 0.09] (0/4,452) |
| zoo_trap:book_clone | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:dies_after_discovery | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:exact_values | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:first_day_of_month | 4 | 0.00 % [0.00, 0.14] (0/2,693) |
| zoo_trap:illiquid_shorts | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:inflated_claim | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:membership_window | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:noise_score | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:repackaged_momentum | 4 | 0.00 % [0.00, 0.14] (0/2,693) |
| zoo_trap:same_date_new_york | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:short_volatility | 4 | 0.00 % [0.00, 0.14] (0/2,693) |
| zoo_trap:survivor_universe | 4 | 0.00 % [0.00, 0.14] (0/2,692) |
| zoo_trap:three_symbols | 4 | 0.00 % [0.00, 0.14] (0/2,693) |

### Honest twins of the cross-sectional traps
| twin | level 6 or above |
|---|---|
| zoo_twin:book_clone | 62.42 % [60.10, 64.68] (1,068/1,711) |
| zoo_twin:dies_after_discovery | 90.59 % [89.11, 91.88] (1,550/1,711) |
| zoo_twin:exact_values | 91.88 % [90.49, 93.08] (1,572/1,711) |
| zoo_twin:first_day_of_month | 75.57 % [73.48, 77.55] (1,293/1,711) |
| zoo_twin:illiquid_shorts | 9.00 % [7.73, 10.45] (154/1,711) |
| zoo_twin:inflated_claim | 10.93 % [9.54, 12.50] (187/1,711) |
| zoo_twin:membership_window | 10.70 % [9.32, 12.25] (183/1,711) |
| zoo_twin:noise_score | 33.78 % [31.58, 36.06] (578/1,711) |
| zoo_twin:repackaged_momentum | 94.39 % [93.20, 95.38] (1,615/1,711) |
| zoo_twin:same_date_new_york | 2.45 % [1.82, 3.30] (42/1,711) |
| zoo_twin:short_volatility | 36.65 % [34.39, 38.96] (627/1,711) |
| zoo_twin:survivor_universe | 13.85 % [12.30, 15.57] (237/1,711) |
| zoo_twin:three_symbols | 96.79 % [95.84, 97.52] (1,656/1,711) |

### Noise by data and K
| data | K | above level 3 |
|---|---|---|
| null_real | 1 | 2.11 % [1.78, 2.50] (129/6,124) |
| null_real | 10 | 2.96 % [2.56, 3.41] (181/6,124) |
| null_real | 100 | 1.37 % [1.11, 1.69] (84/6,124) |
| null_real | 1000 | 0.80 % [0.61, 1.06] (49/6,124) |
| null_scores | 1 | 0.24 % [0.16, 0.36] (22/9,336) |
| null_scores | 10 | 0.02 % [0.01, 0.08] (2/9,332) |
| null_scores | 50 | 0.00 % [0.00, 0.04] (0/9,332) |
| null_sim | 1 | 1.34 % [1.08, 1.66] (82/6,128) |
| null_sim | 10 | 1.01 % [0.79, 1.29] (62/6,128) |
| null_sim | 100 | 0.34 % [0.22, 0.52] (21/6,124) |
| null_sim | 1000 | 0.03 % [0.01, 0.12] (2/6,124) |

### Regime-decay by sample length
| years | above maximum |
|---|---|
| 1 | 1.08 % [0.73, 1.60] (24/2,226) |
| 3 | 3.32 % [2.66, 4.15] (74/2,226) |
| 5 | 6.60 % [5.65, 7.71] (147/2,226) |
| 10 | 19.09 % [17.51, 20.78] (425/2,226) |

### Single-asset power, level 3 or above
| Sharpe | years | rate |
|---|---|---|
| 0.5 | 1 | 30.39 % [29.32, 31.47] (2,127/7,000) |
| 0.5 | 3 | 20.01 % [19.09, 20.97] (1,401/7,000) |
| 0.5 | 5 | 12.77 % [12.01, 13.57] (894/7,000) |
| 0.5 | 10 | 5.91 % [5.39, 6.49] (414/7,000) |
| 1.0 | 1 | 47.90 % [46.73, 49.07] (3,353/7,000) |
| 1.0 | 3 | 47.23 % [46.06, 48.40] (3,306/7,000) |
| 1.0 | 5 | 45.46 % [44.29, 46.63] (3,182/7,000) |
| 1.0 | 10 | 44.59 % [43.42, 45.75] (3,121/7,000) |
| 1.5 | 1 | 64.96 % [63.83, 66.07] (4,547/7,000) |
| 1.5 | 3 | 73.94 % [72.90, 74.96] (5,176/7,000) |
| 1.5 | 5 | 81.76 % [80.84, 82.64] (5,723/7,000) |
| 1.5 | 10 | 89.63 % [88.89, 90.32] (6,274/7,000) |
| 2.0 | 1 | 78.19 % [77.20, 79.14] (5,473/7,000) |
| 2.0 | 3 | 91.94 % [91.28, 92.56] (6,436/7,000) |
| 2.0 | 5 | 96.80 % [96.36, 97.19] (6,776/7,000) |
| 2.0 | 10 | 99.66 % [99.49, 99.77] (6,976/7,000) |

### Single-asset power, level 6 or above
| Sharpe | years | rate |
|---|---|---|
| 0.5 | 1 | 0.34 % [0.23, 0.51] (24/7,000) |
| 0.5 | 3 | 1.36 % [1.11, 1.66] (95/7,000) |
| 0.5 | 5 | 2.01 % [1.71, 2.37] (141/7,000) |
| 0.5 | 10 | 4.23 % [3.78, 4.73] (296/7,000) |
| 1.0 | 1 | 1.49 % [1.23, 1.80] (104/7,000) |
| 1.0 | 3 | 5.84 % [5.32, 6.42] (409/7,000) |
| 1.0 | 5 | 13.96 % [13.17, 14.79] (977/7,000) |
| 1.0 | 10 | 38.00 % [36.87, 39.14] (2,660/7,000) |
| 1.5 | 1 | 4.13 % [3.69, 4.62] (289/7,000) |
| 1.5 | 3 | 20.56 % [19.63, 21.52] (1,439/7,000) |
| 1.5 | 5 | 48.33 % [47.16, 49.50] (3,383/7,000) |
| 1.5 | 10 | 87.04 % [86.24, 87.81] (6,093/7,000) |
| 2.0 | 1 | 8.03 % [7.41, 8.69] (562/7,000) |
| 2.0 | 3 | 47.63 % [46.46, 48.80] (3,334/7,000) |
| 2.0 | 5 | 82.06 % [81.14, 82.94] (5,744/7,000) |
| 2.0 | 10 | 99.57 % [99.39, 99.70] (6,970/7,000) |

### Cross-sectional power by edge
| edge | level 3 or above | level 6 or above |
|---|---|---|
| planted_E1 | 27.81 % [27.07, 28.57] (3,808/13,693) | 0.85 % [0.71, 1.02] (116/13,693) |
| planted_E2 | 91.55 % [91.08, 92.01] (12,532/13,688) | 39.78 % [38.96, 40.60] (5,445/13,688) |
| planted_E3 | 99.42 % [99.28, 99.54] (13,609/13,688) | 79.65 % [78.97, 80.32] (10,903/13,688) |
| planted_E4 | 99.94 % [99.88, 99.97] (13,680/13,688) | 90.85 % [90.35, 91.32] (12,435/13,688) |

### Evidence ceilings
| measure | value |
|---|---|
| Hidden-trials cases capped by missing trial evidence | 100.00 % [99.96, 100.00] (8,912/8,912) |
| Cross-sectional traps stopped at level 5 by the universe check alone | 2,285/35,000 |

### Noise on real bars by asset class
| asset class | years | above level 3 |
|---|---|---|
| commodity | all | 1.40 % [0.85, 2.30] (15/1,070) |
| commodity | 1 | 3.19 % [1.69, 5.95] (9/282) |
| commodity | 3 | 0.83 % [0.28, 2.40] (3/363) |
| commodity | 5 | 0.71 % [0.24, 2.05] (3/425) |
| crypto | all | 4.04 % [3.68, 4.44] (413/10,220) |
| crypto | 1 | 4.11 % [3.53, 4.77] (164/3,994) |
| crypto | 3 | 4.07 % [3.45, 4.80] (136/3,339) |
| crypto | 5 | 3.91 % [3.27, 4.68] (113/2,887) |
| fx | all | 0.08 % [0.04, 0.15] (9/11,338) |
| fx | 1 | 0.66 % [0.35, 1.26] (9/1,354) |
| fx | 3 | 0.00 % [0.00, 0.22] (0/1,782) |
| fx | 5 | 0.00 % [0.00, 0.18] (0/2,078) |
| fx | 10 | 0.00 % [0.00, 0.06] (0/6,124) |
| index | all | 0.32 % [0.15, 0.70] (6/1,868) |
| index | 1 | 1.21 % [0.56, 2.62] (6/494) |
| index | 3 | 0.00 % [0.00, 0.60] (0/640) |
| index | 5 | 0.00 % [0.00, 0.52] (0/734) |

## Software check (P4)
- symmetric cases against parity: 3,062 compared, 0 differ, 0 absent from the reference
- asymmetric cases against silent: 438 compared, 0 differ, 0 absent from the reference
