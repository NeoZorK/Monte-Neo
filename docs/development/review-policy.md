# Ревью при одном мейнтейнере (внутренний документ)

Проект ведёт один человек. OpenSSF Scorecard проверяет «Code-Review» и считает только одобрения **другого человека** (или слияние не тем, кто сделал коммит); ревью ботами и ИИ не считается. Поэтому оценка 0 при одном мейнтейнере честна, и подделывать её (второй аккаунт «для одобрений») нельзя: это именно то, от чего проверка защищает. Ниже — что делаем реально, чтобы ошибки ловились без второго человека, и как получить настоящее ревью.

## Что делаем сейчас (без второго человека)

1. **Все изменения только через PR, `main` защищён обязательными проверками CI** (тесты, verifier 3.11–3.13, docs, Bandit, pip-audit, CodeQL, self-test).
2. **Самопроверка по списку** в шаблоне PR: прочитать весь diff чужими глазами; у изменения поведения есть тест, который без изменения падает; нет чтения секретов/сети/чужого кода без теста; в workflow и Dockerfile — минимальные права, закреплённые версии и хеши.
3. **Независимая проверка ассистентом** (Claude Code, `/code-review`, `/security-review`) перед слиянием изменений в чувствительных путях: `.github/`, `docker/`, `scripts/requirements/`, `verify/signing.py`, `verify/ingest.py`. Это дополнение, а не замена человеческого ревью, и в Scorecard оно не учитывается.
4. **Выдержка**: для чувствительных путей слияние не раньше чем через час после зелёного CI и повторного чтения diff (быстро замеченные ошибки чаще всего находятся при втором чтении).
5. **CODEOWNERS** уже описывает владельца путей; когда появится второй мейнтейнер, достаточно добавить его хэндл и включить правило ниже.

## Как получить настоящее ревью

- **Пригласить соавтора** в Settings → Collaborators (роль Write или Maintain) тому, кому доверяете: коллеге, автору вклада в Trap Suite, мейнтейнеру соседнего открытого проекта. Достаточно одного одобрения на изменения в чувствительных путях.
- **Обмен ревью**: договориться с другим одиночным мейнтейнером открытого проекта («вы смотрите мои PR в чувствительных путях, я ваши»).
- **Приглашение в открытом виде**: issue «Looking for a co-maintainer / reviewer» (текст ниже) с меткой `help wanted`, ссылка в README и в форме вкладов. Участники Trap Suite — естественные кандидаты.
- После появления ревьюера: Settings → Branches → правило для `main` → «Require a pull request before merging» → «Require approvals: 1» и «Require review from Code Owners». Включать только когда ревьюер реально есть, иначе вы заблокируете сами себя.

## Что делать с алертом Code-Review в Security

Пока ревьюера нет: закрыть алерт как **Won't fix** с комментарием «Single-maintainer project. Mitigations: required CI on every change, self-review checklist, assistant review of sensitive paths, CODEOWNERS; a co-maintainer is being sought (docs/development/review-policy.md)». Алерт откроется снова при следующем прогоне Scorecard — это нормально, закрывать его каждый раз не обязательно.

## Текст issue для публикации (английский, публичный)

**Title:** Looking for a co-maintainer / reviewer

**Body:** Monte-Neo is maintained by one person, so no change is reviewed by a second human before it is merged. We would like to fix that. If you review code for a living or for fun and care about trading-strategy verification, we would value a second pair of eyes on pull requests that touch workflows, Docker images, signing and data loading. You would be asked to review, not to write code. Comment here or open a pull request that adds you to `.github/CODEOWNERS`.
