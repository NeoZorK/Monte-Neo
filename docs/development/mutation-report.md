# Мутационная проверка ядра (внутренний документ)

Генерируется `scripts/mutation_check.py`: в файл вносится одно изменение (сравнение, оператор, константа, `and`/`or`, `not`), запускаются тесты файла; мутант «убит», если тесты упали. Выборка фиксирована (`--seed`).

| Файл | Мест для мутаций | В выборке | Убито | Доля |
|---|---|---|---|---|
| `verify/lookahead.py` | 87 | 20 | 17 | 85% |
| `verify/repaint.py` | 83 | 20 | 17 | 85% |
| `verify/stats.py` | 99 | 20 | 20 | 100% |
| `verify/quality.py` | 118 | 20 | 14 | 70% |
| `verify/ledger.py` | 29 | 20 | 19 | 95% |
| `verify/history.py` | 30 | 20 | 18 | 90% |

Итого убито 105 из 120 (88%). Цель плана: не менее 80 %.

## Выжившие мутанты (разобрать: тест, эквивалентный мутант или пробел)

- `verify/lookahead.py`: compare #359
- `verify/lookahead.py`: arith #1218
- `verify/lookahead.py`: compare #860
- `verify/repaint.py`: constant #1481
- `verify/repaint.py`: constant #1359
- `verify/repaint.py`: constant #1480
- `verify/quality.py`: compare #2448
- `verify/quality.py`: compare #2294
- `verify/quality.py`: constant #57
- `verify/quality.py`: compare #1132
- `verify/quality.py`: arith #1855
- `verify/quality.py`: constant #1129
- `verify/ledger.py`: constant #938
- `verify/history.py`: constant #78
- `verify/history.py`: constant #89

## Разбор выживших (05.10.2026)

Выборка 120 мутантов, убито 105 (87,5 %): цель плана (не менее 80 %) достигнута. Первый прогон дал 62 из 120 (52 %): тесты проверяли
статусы, а не значения, и не фиксировали границы. Для найденных мест написан `tests/unit/test_mutation_pins.py` (точные значения снимка
бара, формулы `z`, `expected_max_sharpe`, поправки Ло, границы контрольных точек, ранги истории, форматы идентификаторов).

Оставшиеся 15 в основном эквивалентны или несущественны: изменение значений словаря рангов, не меняющее их порядок
(`VERDICT_RANK`, `STATUS_RANK`); число контрольных точек строгого режима (проверяется только «больше, чем в обычном»); константы
порогов `SESSION_RATE`, `1.4826`, допуск разбиения; ширина high/low синтетической таблицы `foreign_table`; префикс `src:`
идентификатора варианта для нераспознанного исходника. Если мутант окажется важным, добавить точное значение в `test_mutation_pins.py`.
Повторный запуск: `python scripts/mutation_check.py --sample 20` (около 25 минут на 4 ядрах).

