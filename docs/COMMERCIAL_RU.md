# Monte-Neo — коммерческие заметки

Публичное ядро Monte-Neo — **MIT open source** на GitHub:
https://github.com/NeoZorK/Monte-Neo

## Продукт (публичный)

Быстрый локальный research торговых стратегий на Apple Silicon:

- Fee-aware next-bar economics (Metal / Numba; MLX опционально)
- Monte Carlo research helpers
- Paper OMS lane (семантика валидации, не claim «заменить production-бот»)

Установка: `pip install monte-neo` (когда опубликовано) или `pip install "monte-neo[apple]"` на Apple Silicon.

## Что остаётся коммерческим / private

Отдельно от MIT-дерева (не смешивать в публичные релизы):

- Private bake-off harness и peer-сравнения
- Студийные ноутбуки и проприетарные стратегии
- Платный support, кастомные интеграции, OEM / white-label

## Тиры (сервисы, не вторая лицензия на MIT-ядро)

1. **OSS / MIT** — свободно использовать и форкать публичный пакет
2. **Support & consulting** — отдельное соглашение
3. **OEM / white-label** — кастомная упаковка по контракту

## Native Metal

```bash
uv sync --extra apple
uv run bash scripts/build_native.sh
```

См. [METAL_NATIVE_BUILD.md](METAL_NATIVE_BUILD.md).
