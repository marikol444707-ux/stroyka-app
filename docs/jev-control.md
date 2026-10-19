# Управляемый Jev на отдельном сервере

Адрес SSH задаётся локальным профилем `stroyka-dev-agent`. Учётная запись —
`stroyka`, ключ хранится только в SSH. Клиент не читает секреты сервера.

Команды для агента из корня репозитория:

```bash
python3 scripts/jev_control.py status
python3 scripts/jev_control.py demo
python3 scripts/jev_control.py avito --query 'кирпич б/у'
```

Пользователь ставит задачу в чате; агент выполняет эти команды сам.
Доступны только демонстрация и согласованный публичный поиск по Авито в
Ставропольском крае. Это не универсальный доступ к произвольным сайтам.
`observed_unverified` — наблюдение страницы, не доказательство правильного
подбора объявлений. Защитная проверка сайта возвращает отдельный статус;
капчи не решаются, записи не создаются, поставщикам сообщения не отправляются.

## Изоляция и стабильность

- `stroyka-jev-control` создаётся отдельно от старых QA-экспериментов.
- Базовый образ фиксирован точным ID в `scripts/install_jev_control.py`.
  Меняется только слой с `control_task.py`; зависимости не обновляются.
- Docker `--init` собирает завершённых потомков; `unless-stopped` возвращает
  контейнер после сбоя процесса или запуска Docker.
- Нет cookies «Стройки», подключения к БД и исходного общего worker-token.
  Timeweb-ключ и выбранная текстовая модель остаются на сервере. У Chrome
  отдельный UID; исходный entrypoint удаляет ключи из его окружения.
- Существующий `CHROME_NO_SANDBOX=1` сохраняется, не объявляется исправленным.
  Этот отдельный тестовый контур не подтверждает пригодность для production.
- У каждой задачи новое имя посредника browser-harness и отдельный
  BrowserContext. При завершении они закрываются. Уборка, время и шаги ограничены.
- Проверка состояния создаёт пустую вкладку, проверяет её настройку и выполнение
  выражения, затем закрывает контекст. Она не использует модель и внешние сайты.
- Файловая блокировка исключает параллельные задачи и перезапуск во время
  задания. Неизвестный результат никогда не вызывает автоматический повтор задачи.
- Таймер проверяет браузер каждые 30 секунд. После трёх неудачных проверок
  перезапускает только этот контейнер, максимум три раза за час. Исчерпание
  лимита остаётся видимой ошибкой, не бесконечным циклом перезапусков.

## Установка и проверка

Установка выполняется владельцем/агентом только на согласованном отдельном
сервере Jev. Это не установка на сервер приложения «Стройка».

`sudo python3 scripts/install_jev_control.py` создаёт новый контейнер и
устанавливает управляющий скрипт. Установщик не включает таймер и не останавливает
старые контейнеры. Повторная установка поверх существующего контроллера запрещена.
Секретный env-файл создаётся с правами 0600 после сборки образа и удаляется.

Перед включением таймера необходимы: проверка реального renderer, две
последовательные демонстрации с независимой проверкой DOM, проверка уборки
процессов, восстановление после остановки Chrome. После этого разместить
`ops/systemd/stroyka-jev-control.{service,timer}` в `/etc/systemd/system`, выполнить
`systemctl daemon-reload` и `systemctl enable --now stroyka-jev-control.timer`.

Последний результат и состояние восстановления хранятся только у root в
`/var/lib/stroyka-jev-control/last.json` и `watchdog.json`.
Откат: отключить таймер и остановить `stroyka-jev-control`; старые контейнеры
не удаляются установщиком и могут быть запущены явно. Секретные inspect-данные
не сохраняются в Git и не печатаются в отчёт.

## Server tools, 19 October 2026

`sudo stroyka-jev status|demo|avito|eis` is the fixed standalone entry point.
The first three use the already-installed bounded controller. `eis` launches a
separate temporary browser without model keys, production connections or personal
sessions, verifies the pinned public CA and reads only the public search registry.
It does not execute a keyword/region search or select procurements. The result
explicitly keeps `search_execution_verified=false`. A valid registry, search field
and observed notice links are required; an HTTP error/homepage is not success.

Install a reviewed release's scripts, public CA and documentation under
`/opt/stroyka-jev-tools/releases/<commit>`, with a SHA-256 manifest. The root-owned
`current` symlink selects the release; `/usr/local/bin/stroyka-jev` invokes its
`scripts/jev_server_tools.py`. Existing Jev service and recovery timer stay intact.
Only this tools directory and launcher need reverting/removing for rollback;
there are no database or application migrations. Local Mac browser/profile code
remains Mac-specific and is retained as source, not enabled as a Linux service.

`sudo stroyka-jev eis-search --query 'электромонтаж'` submits the observed public
GET form in the temporary browser. It retains the site's own form parameters.
The returned URL and rendered search input must independently preserve the query,
and the registry must contain first-party notice links. This verifies keyword
search execution, not relevance, deadlines, regional fit or bid suitability.
`region_verified=false` remains explicit. No model calls, login or bid submission.
The observed form worked where hand-assembled query URLs returned HTTP 404; the
precise server-side reason for that difference is not established.

Further live tests found an empty-result handling bug: EIS displays both
`0 записей` and `Поиск не дал результатов`. These now confirm a successful empty
keyword search only when the URL and input agree and no notice links exist. The
runtime checks rendered `innerText`, so hidden templates are not empty-result
evidence. Worker failures now retain their structured status instead of being
flattened to `runner_failed`; stdout/exit-code inconsistencies remain failures.
Successful search output also includes up to ten observed first-party notice URLs.

A captured live traceback located intermittent OSError 39 failures in profile
cleanup after a successful search: Chrome descendants were still writing while
Python's TemporaryDirectory removed `chrome/Default`. Scratch now lives until the
one-shot container exits; Docker's `--rm` and the host's unconditional named
container removal own teardown. No shared/persistent browser profile is involved.
A regression simulates the late cleanup error and requires keeping the verified
result. This is not an automatic retry of a search or a suppression of worker errors.

## Stavropol open applications (44-FZ)

`sudo stroyka-jev eis-search --query 'капитальный ремонт' --stavropol-open`
uses the observed advanced search form. It selects only 44-FZ and `Подача заявок`
and fills `Местоположение поставки (ГАР)` with `Ставропольский край`. It does not
filter by the customer's address. URL parameters and the rendered input/checked
controls must independently retain these settings. A dropped filter fails closed.

`delivery_region_filter_verified` and `active_only_filter_verified` describe the
search filters, not independently verified notice contents. `region_verified`
remains false at the generic search-result level. Returned first-page notice URLs
still need individual checks for delivery place, stage and exact deadline.
The flag does not cover 223-FZ or procurement under government decree 615.
It does not assess bidder eligibility or automatically submit applications.

## Следующий этап: документы закупки

Проверка оригиналов, OCR, смет, требований и подготовка короткого отчёта
зафиксированы в [плане](../tasks/jev-procurement-documents-plan.md).
Первая версия обработчика описана в [руководстве](jev-procurement-documents.md);
полная проверка смет и профиля участника остаются в плане.
