# Срез 2д3 — полный вход в рабочее место поддержки

При включённом новом режиме сотрудник поддержки входит через обычную форму
с паролем и кодом 2FA. Он видит назначенные обращения, открывает диагностику,
обновляет список и выходит. Общие данные компании при этом не загружаются.
Разработка и проверка локальные; production, публикация и включение не выполнялись.

## Что исправлено

Раньше App открывал отдельный экран уже после запуска общих hooks: загрузки
компаний, проектов, журнала работ и presence. Теперь единый UI predicate
`isSupportWorkspaceUser` исключает общий bootstrap, запрос company-context,
чтение бизнес-кэша в bootstrap, push/presence и отложенные загрузки разделов.
Журнал событий и нормы также не загружаются, даже если предыдущий пользователь
оставил соответствующий раздел открытым. Серверные проверки остаются основой
полномочий; этот UI predicate только выбирает экран и убирает лишние запросы.
Default-off поведение других ролей и прежнего режима сохранено.

Company context скрывает данные прежнего пользователя уже при новом render,
отменяет предыдущий запрос и проверяет поколение ответа после fetch/json.
Последний refresh побеждает; старый запрос не меняет выбор, ошибку, loading
или сохранённую компанию. Отзыв страницы отменяет запрос. Выбор в памяти
сохраняется и при недоступном browser storage. Поздние bootstrap callbacks
не меняют loading/push после выхода. SupportWorkspace получает key текущего
пользователя: при смене сотрудника очищаются список, диагностика и pending reads.
Это не универсальная отмена всех бизнес-запросов других экранов.

Проверка повторного входа выявила отдельно старый кэш CSRF. При начале/успехе
login/2FA и успешном logout кэш сбрасывается. Поздний CSRF lookup не может
передать прежний код новой сессии; ожидающая его старая mutation завершается
AbortError до отправки. Поздний HTTP-ответ прежнего поколения не запускает
frontend logout/alert для новой сессии. Уже отправленные запросы и изменения
cookies другими вкладками не отменяются; межвкладочная синхронизация и общая
очередь конкурирующих login/logout не входят в этот срез.

## Приёмка

- RED: воспроизведены ненужный bootstrap, старый company response, прежние
  loading/push callbacks, CSRF повторного входа и оставшийся activitylog.
- Focused unit проверяет company context/refresh/storage/смену пользователя,
  bootstrap и presence, API CSRF и полный App с dashboard/estimates/activitylog.
  Actual AppEntryRoutes + actual lazy SupportWorkspace проверяют смену двух
  сотрудников одной роли и позднюю диагностику первого.
- PostgreSQL: новый cookie login тест + 17 capability tests, 18 PASS без skips.
  Настоящие password hash/TOTP, challenge без session cookie, HttpOnly cookie
  после 2FA, reload, свой diagnostic, чужой 404, business 403, logout с CSRF,
  missing-CSRF 403 и replay отозванной cookie 401. Два сотрудника, разные списки.
  Обязательность CSRF включена явно в изолированном runtime: базовый fixture
  намеренно заменяет окружение, поэтому внешний env не считается доказательством.
- Полный frontend: 304 suites / 1869 tests PASS; production build
  Compiled successfully, без ESLint warnings. Сохранились прежние предупреждения
  Browserslist, Node fs.F_OK и большой размер bundle. Полный backend discovery
  повторно не запускался; проверены 18 профильных PG tests и Python compile.
- Chromium: настоящий login/2FA, свой diagnostic, reload, logout, второй
  сотрудник без обращений и повторный logout. В обоих случаях logout 200,
  CSRF lookup выполнен отдельно для каждой сессии. Ноль company-context и
  work-journal запросов; единственный projects запрос — намеренная проба 403.
  320/390/768/1440 px без горизонтального overflow; мобильный скриншот просмотрен.
  Нет ошибок JavaScript; ожидаемый console HTTP 403 от отрицательной пробы
  и прежнее предупреждение preload публичного изображения не являются сбоем UI.

Логи: `/tmp/support-bootstrap-accepted-full-frontend.log`,
`/tmp/support-bootstrap-accepted-build.log`, `/tmp/support-login-final-pg.log`
(1 login + 17 capabilities), `/tmp/support-cookie-accepted-pg.log`
(новый login после проверки CI-инвентаря). Новый тест включён в mandatory PG CI;
CI и production здесь не запускались. Review пяти осей: startup predicate общий,
без дублирования правила входа; scope/generation защищает старый state;
backend authority неизменна; меньше запросов, без новой загрузки архивов;
границы межвкладочной синхронизации и отправленных запросов описаны явно.

Browser использует настоящий production App/index/lazy chunks и настоящий HTTP
backend через loopback proxy к Unix socket. Authorization/session headers не
подставляются; cookie выдаёт login/2FA. Все пользователи и компании синтетические,
PostgreSQL отдельный socket-only, исходящая backend сеть/SMTP/S3 запрещены.
Скриншоты в игнорируемом output/playwright/participant-support; приватные
временные настройки удаляются, браузер и тестовые серверы останавливаются.

## Следующие блоки

Корректирующая операция ошибочной связи требует отдельный точный preview:
какие документы и доступы затронуты, версии/epochs, подтверждённое последствие,
атомарная команда и аудит; универсальный undo недопустим. Также остаются обзор
platform-level отказов без grant, физический storage/CDN readiness и нагрузка/
company-scoped writer locks для исторического merge, затем этапы 3–5.
Этот срез не делает весь многоклиентский контур готовым к production.
