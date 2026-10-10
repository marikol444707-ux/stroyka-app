# JEVA: автономная QA-проверка без оператора

## Что уже автоматизировано

Один раз в день systemd запускает **только read-only smoke** через локальный
QA worker на `127.0.0.1:18088`. Worker открывает
`https://stroyka-qa-gateway/app` и проверяет наличие меню `Склад`.
В scheduled read-only режиме цикл действий Jev (`agent.run()`) вообще не
запускается: доступны только наблюдение DOM/URL и детерминированная проверка.
Тест считается успешным только при проверках
`read_only_observation`, `expect_text[0]:present`,
`expect_url_contains[0]:present` и отсутствии ошибок/boundary violations.

Это **не** полноценный автономный тест перемещения. Он отдельно потребует
изолированных тестовых данных, подтверждения тела запроса, проверки БД и
семантики ожидаемого отказа. Не следует засчитывать `failed` как PASS
только потому, что HTTP 400 и БД не изменилась.

## Что система НЕ делает

- Не открывает production и не запускает миграции/деплой.
- Не получает доступ к Docker socket, БД, SSH, сессии пользователя или ключу Timeweb.
- Не обновляет автоматически образы JEVA.
- Не публикует скриншоты, введённые значения, секреты или сырые ошибки модели.
- Не отправляет уведомления без отдельного токена GitHub.
- Не запускает несколько браузерных задач одновременно (worker имеет очередь).

## Однократная установка (только после review и проверки PR)

На QA-сервере, из проверенной версии репозитория:

```bash
sudo bash scripts/install_jev_qa_watch.sh
```

Установщик не изменяет Docker-контейнеры, Caddy и production. Под `root`
он однократно читает сильный `DEV_CONTROL_API_TOKEN` из
`/etc/stroyka-jev-qa.env`, выводит из него односторонний scoped
`JEV_WATCHER_TOKEN` и записывает в `/etc/stroyka-jev-watch.env`
**только scoped read-only credential** и порт 18088. Общий worker-token,
ключ Timeweb и QA session туда не копируются.

Watcher подписывает каждый запрос к фиксированным `/watcher/*` endpoint'ам
HMAC по method/path/timestamp/nonce/body hash. Сервер сам формирует
фиксированный read-only smoke; scoped credential не авторизует общий
`/jobs`. Сам watcher выполняется под пользователем `stroyka`, а не root.

```bash
systemctl list-timers stroyka-jev-watch.timer
sudo systemctl start stroyka-jev-watch.service
sudo cat /var/lib/stroyka-jev-watch/last.json
```

По умолчанию таймер работает ежедневно в **08:00 по часовому поясу сервера**
с разбросом до 15 минут. Изменить расписание можно отдельным override
systemd. При выключенном сервере `Persistent=true` запускает пропущенную
проверку после включения.

При неуспехе watcher возвращает код 1 и фиксирует только категорию ошибки
в `/var/lib/stroyka-jev-watch/last.json`. Подробности доступны в
защищённом worker evidence (TTL ограничен). Для диагностики:

```bash
sudo journalctl -u stroyka-jev-watch.service -n 30 --no-pager
```

## Уведомления в GitHub (необязательно)

Для автоматического комментария в задаче #311 нужен отдельный
**fine-grained GitHub token** только с разрешением `Issues: Read and write`
для репозитория `marikol444707-ux/stroyka-app`.
Добавить его как `JEV_WATCH_GITHUB_TOKEN=...` в
`/etc/stroyka-jev-watch.env` (не в репозиторий, не в goal, не в логи).
Токен хранится на сервере, `root:stroyka`, mode 0640.
Без него отчёт остаётся локальным, поэтому удалённые уведомления пока
не гарантируются.

Watcher отправляет **только** UTC-время, идентификатор задания,
результат, коды проверок и обобщённые категории ошибок. Запрос идёт
только на фиксированный endpoint GitHub issue #311.

## Перед полноценной автономией

1. Закрепить Caddy static QA route в постоянном конфиге (текущий reload временный).
2. Заменить краткосрочный Chrome SPKI pin на доверие к QA CA.
3. Убедиться, что на сервере активен только один QA worker, не множество
   экспериментальных Chrome.
4. Провести несколько последовательных успешных read-only smoke.
5. Отдельно разработать сценарии склад/снабжение/проекты с детерминированными
   проверками и тестовой ролью, не имеющей доступа к production.

Откат автоматизации: `sudo systemctl disable --now stroyka-jev-watch.timer`.
Это не удаляет worker и не затрагивает приложение.
