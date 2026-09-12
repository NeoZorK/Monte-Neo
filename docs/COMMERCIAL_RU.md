# Monte-Neo — коммерческая модель (internal)

Версия **private**. Репозиторий **не публичный**. GitHub удалён.

## Продукт

Monte-Neo — framework генерации и валидации торговых индикаторов:

- Monte Carlo / walk-forward / robustness pipeline
- MLX Tier-1 screen, Numba path-dependent metrics
- Metal GPU acceleration (Apple Silicon): `metal_engine`, `MetalFloat8Engine`

## Дистрибуция

| Канал | Статус |
|---|---|
| GitHub | **удалён** — не open source |
| NeoZorK gitserver | `/Users/rostsh/git-server/NeoZorK/Monte-Neo.git` |
| LAN | `ssh://rost@2014/Users/rost/git-server/NeoZorK/Monte-Neo.git` |

## Модели лицензирования

1. **Internal studio** — R&D внутри NeoZorK (Wave2, PHL, и др.)
2. **Commercial license** — отдельное соглашение для внешних клиентов
3. **OEM / white-label** — индикаторный генератор без Wave2

## Vendoring (QWC_WAVE2)

QWC_WAVE2 **не импортирует** `monte_neo` как pip dependency (ADR-0009).
Разрешён vendoring фрагментов с docstring: путь gitserver + commit hash.

## Сборка native

```bash
uv sync
uv run bash scripts/build_native.sh
```

См. [METAL_NATIVE_BUILD.md](METAL_NATIVE_BUILD.md).
