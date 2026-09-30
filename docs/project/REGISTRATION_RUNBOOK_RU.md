# Регистрация Monte-Neo в каталогах — пошаговый runbook (внутренний документ)

Всё ниже делается с вашего аккаунта: я не могу входить в чужие сервисы и открывать PR в чужие репозитории. Тексты готовы, время на всё — около 60–90 минут. Порядок — от самого выгодного к менее выгодному.

Правила для всех текстов: только то, что читатель может воспроизвести; «проверяет методологию, а не обещает прибыль»; не называть чужие проекты по имени.

## 0. Уже сделано автоматически

- Официальный реестр MCP (`io.github.NeoZorK/monte-neo`) — обновляется при каждом выпуске (job `mcp-registry`).
- PyPI, GitHub Release + SBOM, образ в GHCR.

## 1. GitHub Marketplace для Action (5 минут)

1. Репозиторий → Releases → откройте последний выпуск (v0.46.0) → Edit.
2. Отметьте «Publish this Action to the GitHub Marketplace».
3. Категории: `Testing` и `Code quality`. Примите условия Marketplace (один раз).
4. Save. Название Action уникально в Marketplace: `Monte-Neo strategy verify`.
5. Дальше галочку нужно ставить при каждом выпуске, если хотите, чтобы новая версия обновилась в Marketplace.

## 2. Каталоги MCP (по 3–5 минут)

| Каталог | Что делать |
|---|---|
| Glama (glama.ai) | Войти через GitHub → «Add server» → URL репозитория. В репозитории есть `glama.json`: нажать «Claim» как владелец. |
| Smithery (smithery.ai) | Войти через GitHub → «Add server» → выбрать репозиторий Monte-Neo. |
| mcp.so | «Submit» → GitHub URL + описание (ниже). |
| MCP Market (mcpmarket.com) | Форма «Submit» → GitHub URL + описание. |
| PulseMCP | Берёт данные из официального реестра сам. Через день проверьте, что запись появилась; если нет — форма «Submit» на сайте. |

Описание (одна строка): `Verify trading-strategy backtests: look-ahead probes, costs, Deflated Sharpe, signed reproducible certificates. MCP server, CLI, GitHub Action.`

## 3. Awesome-списки (PR со своего аккаунта, по 5 минут)

Для каждого: Fork → правка `README.md` → Pull request с заголовком `Add Monte-Neo`. Читайте CONTRIBUTING списка: у некоторых обязателен порядок по алфавиту и эмодзи.

1. **awesome-mcp-servers** (punkpeye/awesome-mcp-servers), раздел «Finance & Fintech»:
   `- [NeoZorK/Monte-Neo](https://github.com/NeoZorK/Monte-Neo) 🐍 🏠 - Verify trading-strategy backtests: look-ahead probes, costs, Deflated Sharpe, signed certificates.`
2. **awesome-quant** (wilsonfreitas/awesome-quant), раздел «Python → Backtesting»:
   `- [Monte-Neo](https://github.com/NeoZorK/Monte-Neo) - Verifier for backtests: look-ahead bias, costs, Deflated Sharpe, reproducible certificates.`
3. **awesome-systematic-trading** (paperswithbacktest/awesome-systematic-trading), раздел инструментов:
   `- [Monte-Neo](https://github.com/NeoZorK/Monte-Neo) - Independent verifier for backtests: look-ahead probes, costs, Deflated Sharpe, reproducible certificates.`

## 4. conda-forge (20 минут)

1. Fork `conda-forge/staged-recipes`.
2. Создать `recipes/monte-neo/meta.yaml` из `packaging/conda-forge/meta.yaml`. Версию и `sha256` обновить на актуальные из PyPI (страница выпуска → Download files → sdist → hashes).
3. PR. Проверки соберут рецепт. Если `mcp` нет в conda-forge — скажите мне, сделаю его необязательным.
4. После слияния вы — мейнтейнер `monte-neo-feedstock`; новые версии предлагает бот.

## 5. Настройки репозитория (10 минут)

Settings → General: включить Discussions; загрузить social preview `docs/assets/social-preview.png`; Topics и About из `docs/marketing/launch-kit.md`.
Settings → Code security: включить Private vulnerability reporting, Secret scanning, Push protection, Dependabot alerts.
Settings → Branches: защита `main` (обязательные проверки CI).
Packages → `monte-neo-verify` → Package settings → сделать публичным (если ещё нет).

## 6. Публикации (когда будет готов первый прогон Honesty Bench)

Show HN, r/algotrading, X/LinkedIn — тексты в `docs/marketing/launch-kit.md`. «Ловушка недели» — раз в неделю из `docs/marketing/trap-of-the-week.md`.
