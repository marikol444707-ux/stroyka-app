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

## Commercial construction leads across public platforms

`python3 scripts/jev_control.py commercial-search` runs a one-time, public,
read-only search for current construction, repair and finishing procedure
candidates in the Stavropol region across eight sources: B2B-Center, Roseltorg,
Fabrikant, ETP GPB, Sber AST, TЭК-Торг, Торги Федерации and Р-ТЕНДЕР.
It searches construction and repair wording variants such as construction and
general construction works, capital repair/капремонт, current repair,
reconstruction, finishing, landscaping, façade and roofing work, engineering
networks, electrical installation, road work and asphalting. The queries are
paired with regional/city names where the source supports text search. The
matching rules recognize abbreviations such as СМР and alternate spellings;
they still exclude materials-only purchases and equipment repair where the
title makes that distinction clear.

B2B-Center searches twelve regional city/region names plus fourteen work-title
phrases: construction, capital/current repair, repair, finishing, installation,
landscaping, reconstruction, electrical installation, roofing, foundations,
капремонт, engineering networks and façade work. It verifies the rendered query
and current-results tab, then checks the returned procedure's region and work
description. Roseltorg searches Stavropol and fourteen construction phrases in
its Stavropol-region filter and open commercial/223-FZ section. Fabrikant uses its public commercial section
and Stavropol customer-region filter. ETP GPB uses its public API, resolves
Stavropol Krai from the public regions list, and reads active applications only.
Sber AST runs five bounded searches (`Ставрополь`, capital repair, капремонт,
construction and Stavropol Krai reconstruction) in the public
`Торги коммерческих заказчиков` source, checking
the search phrase and active deadline range in the request and rendered page.
TЭК-Торг searches its combined 223-FZ/commercial section for active procedures
with future deadlines. Торги Федерации uses its commercial section and active
statuses, searching regional wording in procedure titles. Р-ТЕНДЕР limits its
public search to commercial purchases with applications in progress and checks
regional wording in the title. Results are deduplicated by source and procedure
ID. Only bounded first pages are read; some sources use a customer-region filter
or title text rather than a verified worksite filter.

B2B-Center exposes keyword search without sign-in, but its public form says
additional filters and saved templates require registration. Fabrikant's
public filter is by customer region, not the worksite, so the actual place and
deadline remain for review. Roseltorg's public source combines commercial and
223-FZ records; the procedure regime must be verified in the original, and its
region filter describes the customer region. These cases remain in “Нужно
проверить”. Results show the source and original procedure link. Search coverage
is partial and does not replace paid aggregators, private buyer portals, or
second and later pages. Details and participation may require a separate
account or tariff. Jev does not register, pay, download restricted files,
contact organizers, or submit an offer. ETP GPB uses the public API exposed by
its procedures page, resolves Stavropol Krai from the public regions list, and
reads active applications only. Its `Закупки.Бизнес` category is classified as
commercial; `Бизнес223` and `Гос44` are excluded, while broad or unknown
categories remain for review. No LLM is called for this search. The platform
roadmap and remaining checks are in
[the commercial search plan](../tasks/jev-commercial-search-plan.md).

Sber AST uses the public `Торги коммерческих заказчиков` source and checks that
the exact source, search phrase, and current-to-one-year application deadline
range were sent in the request and remain selected in the rendered page (the
site removes the query from the address bar after loading it). It reads a
bounded set of first-page searches. Sale, resale, and rental procedures are
excluded; unknown procedure types require review. The Stavropol region is
checked in the visible work description because this search has no verified
worksite-region filter.

Р-ТЕНДЕР runs twelve regional/city title queries in its public commercial
applications-in-progress filter. The browser stays connected for the complete
search; a disconnected browser invalidates that source's results.

TЭК-Торг reads the server-rendered public listing in its combined
`223-ФЗ и Коммерческие закупки` section. First-page searches cover Stavropol
construction, capital repair/капремонт, finishing and landscaping, plus
Nevinnomyssk repair and construction. Only rows marked
`Приём заявок` with a future submission deadline and construction-related
title are considered. A region found only in the title remains for manual
verification; the combined section does not prove a commercial legal regime,
so these rows are never automatically called confirmed commercial purchases.
Search URL, section, result counts and empty-state shape are checked before an
empty result is reported. The search is partial: a lack of matches in these
queries does not mean the whole platform has no current procedures.

## Следующий этап: документы закупки

Проверка оригиналов, OCR, смет, требований и подготовка короткого отчёта
зафиксированы в [плане](../tasks/jev-procurement-documents-plan.md).
Первая версия обработчика описана в [руководстве](jev-procurement-documents.md);
полная проверка смет и профиля участника остаются в плане.
