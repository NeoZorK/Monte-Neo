# Кандидаты на очистку (внутренний документ)

Статус: **выполнено в v0.26.0** по одобрению владельца (NeoZorK): группы A, B и C. Данные собраны на ветке после v0.22.0.

## A. Безопасно удалить (мусор в репозитории)

| Путь | Доказательство | Риск |
|------|----------------|------|
| `profile_stats.txt` (8.5 KB) | Вывод профайлера; указан в `.gitignore`, но всё равно закоммичен; кода, который его читает, нет | Нет |
| `exports/` (18 файлов, 96 KB) | Артефакты локального прогона (`certificate_DynamicIndicator_CERT-…md`, `production_indicator.cpp`); `exports/` указан в `.gitignore`, но файлы закоммичены | Нет: каталог создаётся заново при экспорте |
| `verify_gpu_optimizer.py` (корень) | Ни одной ссылки в коде, тестах или документации | Нет |

## B. Перенести, а не удалять

| Путь | Доказательство | Предложение |
|------|----------------|-------------|
| `verify_hardware.py` (корень) | Упоминается в `docs/METAL_NATIVE_BUILD.md` и `docs/setup/development-setup.md` | Перенести в `scripts/`, обновить две ссылки |
| `scripts/test_dlpack.py`, `scripts/test_mlx_overhead.py`, `scripts/test_mlx_ptr.py`, `scripts/verify_metrics_accuracy.py`, `scripts/benchmark_3d_engine.py` | Нет ссылок; разовые эксперименты с Metal/MLX; имя `test_*` путает с pytest | Удалить или перенести в `scripts/experiments/` |
| `scripts/test_advanced_metal.py`, `scripts/test_bb_metal.py`, `scripts/test_metal_pipeline.py` | Одна ссылка (docs-map) | То же, обновить docs-map |

## C. Требует решения (не мусор, но вне фокуса продукта)

| Область | Доказательство | Варианты |
|---------|----------------|----------|
| `tests/unit/test_coverage_boost*.py` (16 файлов, 6 641 строка) | Названы по цели «добрать покрытие», а не по поведению; дублируют тематические тесты | Постепенно разнести по тематическим файлам. Удалять целиком нельзя: упадёт покрытие |
| Генератор индикаторов + MLX/3D-движок (`core/`, `indicators/`, MLX-части `backtest/`) | Верификатор импортирует из `backtest/` только `bar_engine`, `model` и `export_signals`; всё остальное не нужно ни ему, ни MCP (ленивые импорты с v0.21.0); только macOS/Metal. Вместе с `backtest/` это около 380 KB исходников | Оставить, но заморозить: только исправление багов. Возможен вынос в extra `monte-neo[research]` |
| `oms/` (около 90 KB исходников), `policy/` | Используются в меню CLI и документации; не связаны с верификатором | Оставить; пересмотреть после публичного прогона Honesty Bench |
| `user_indicators/`, `config.yaml` | Используются интерактивным меню (`cli/menu/*`) | Оставить |

## Что сделано (v0.26.0)

- **A:** `profile_stats.txt`, `exports/` и `verify_gpu_optimizer.py` удалены из дерева.
- **B:** `verify_hardware.py` перенесён в `scripts/`; восемь разовых экспериментов — в `scripts/experiments/` (с README); ссылки обновлены.
- **C:** побочные полосы заморожены (раздел «Frozen lanes» в `docs/development/contributing.md`). `test_coverage_boost*.py` перенесены в `tests/unit/legacy_coverage/` с README: это страховочная сеть для замороженного кода, новые тесты пишутся в тематические файлы. `oms/`, `policy/`, `user_indicators/` и `config.yaml` оставлены: их использует меню CLI.

## Исходный порядок

1. Группа A: одним коммитом `chore: remove tracked build artifacts`.
2. Группа B: перенос с обновлением ссылок; `test_maintenance` проверит docs-map.
3. Группа C: отдельные задачи в ROADMAP, без удаления.
