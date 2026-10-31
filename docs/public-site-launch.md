# Запуск публичного сайта

Короткий чеклист перед открытым запуском `https://stroyka26.pro`.

## Текущее состояние

- 2026-10-31: production главная страница и health endpoint отвечали `200`; `/site/projects` и `/site/pricing` загружались в браузере, ошибок JavaScript не было.
- На ширине телефона до 420 px меню занимало слишком много места: шесть ссылок располагались одним столбцом. Исправление подготовлено в отдельной ветке; оно вступит в силу после выпуска.
- Отправка формы в production не проверялась, чтобы не создавать реальную заявку в CRM. После подтверждения тестового адреса или отдельного тестового режима нужно проверить путь до CRM.
- Контактные адреса и реквизиты оператора не подтверждены. До подтверждения не запускать рекламу и массовую отправку персональных данных.

## Что уже должно работать

- Главная страница открывается без авторизации.
- Форма заявки создает лид в CRM и задачу директору.
- Форма партнёрской заявки создает лид в CRM на проверку и не выдает активный доступ автоматически.
- Блоки `Объекты`, `Наши работы` и `Референсы` разделяют опубликованные объекты, доказательства выполнения и направления для будущих заявок.
- В заявке фиксируются согласие на обработку персональных данных, страница, IP, User-Agent, referrer и UTM-метки.
- Есть `robots.txt`, `sitemap.xml`, `llms.txt`, PWA manifest, SEO/OG-мета и JSON-LD для поисковиков, мессенджеров и AI-агентов.
- Есть статические публичные страницы для индексации без входа в ERP: `/features.html`, `/project-catalog.html`, `/contacts.html`, `/privacy.html`, `/terms.html`.
- `npm run smoke:public-site` сверяет React-каталог, статический `/project-catalog.html` и локальные файлы проектных медиа, чтобы перед деплоем не проходили карточки без фасада, второго ракурса или планировки.
- Каждая карточка статического каталога должна вести на интерактивный проект: `/?project=H1-01#projects`, `/?project=B1-01#projects` и так далее.
- Статическая карточка проекта в `/project-catalog.html` должна сразу показывать площадь, этажность/формат, краткую планировку и состав визуалов, чтобы каталог был читаемым без React.
- `/project-catalog.json` отдает те же 15 направлений и 45 проектов в машинно-читаемом виде для AI-поиска, интеграций и автопроверок, включая статус `Проект-идея / пример для расчета`, площадь, этажность/формат, планировку, состав визуалов, полный `media[]` по каждому проекту и deep-link URL.

## Перед рекламой и публикацией

### Уведомления о заявках

Публичная форма сохраняет заявку и задачу «Связаться с заявителем» в CRM. После успешного сохранения backend может отправить короткое уведомление на рабочую почту. Письмо не содержит комментарии формы, IP-адрес, User-Agent или вложенные документы; оригиналы остаются в CRM. Ошибка SMTP не отменяет сохранённую заявку.

Чтобы включить письма, задайте в серверном окружении backend:

```dotenv
PUBLIC_SITE_LEAD_EMAIL_ENABLED=true
PUBLIC_SITE_LEAD_EMAIL_TO=фактический-рабочий-адрес@example.ru
SMTP_HOST=адрес-SMTP-сервера
SMTP_PORT=465
SMTP_USER=учётная-запись-SMTP
SMTP_PASSWORD=пароль-SMTP
SMTP_FROM=адрес-отправителя@example.ru
SMTP_SSL=true
SMTP_TLS=false
```

Для SMTP с STARTTLS используйте порт 587, `SMTP_SSL=false` и `SMTP_TLS=true`. Не отправляйте SMTP-пароль в чат и не добавляйте его в Git. Перед включением замените примеры реальными параметрами почтового провайдера. После изменения окружения перезапустите backend. Пока уведомление выключено или SMTP не настроен, заявки по-прежнему сохраняются в CRM без письма.

- Создать рабочие ящики `privacy@stroyka26.pro` и `info@stroyka26.pro` или заменить их в `src/components/PublicSitePage.jsx` на фактические.
- Подтвердить фактического оператора персональных данных: юрлицо или ИП, ИНН/ОГРН, юридический адрес.
- Добавить полные реквизиты в договор/коммерческое предложение. Если юрист требует выводить их на сайт, добавить их в блок `PUBLIC_SITE_OPERATOR`.
- Проверить текст согласия и политику обработки персональных данных с юристом под фактическое юрлицо.
- Перед рекламой перевести калькулятор с hardcode-ставок на управляемый прайс по плану `docs/public-site-calculator-pricing.md`.
- Для галереи использовать реальные фото, лицензированные изображения или AI-примеры с пометкой `пример`; не публиковать Pinterest-картинки как выполненные работы.
- Проектные карточки каталога до утверждения считать примерами для расчета, а не реальными готовыми проектами, договорами, актами или накладными.
- Перед визуальной доработкой выбрать подачу из `docs/public-site-packaging-variants.md`.
- Проверить, что SSL, DNS, редирект с `www` и `https` работают.
- Перед рекламой включить DDoS-защиту по плану из `docs/ddos-and-ai-indexing.md`.
- Открыть сайт с телефона и проверить: первый экран, калькулятор, форма заявки, юридический блок.
- Отправить тестовую заявку с UTM: `https://stroyka26.pro/?utm_source=test&utm_medium=manual&utm_campaign=launch`.

Без подтверждённых реквизитов и политики не запускать рекламу и массовый трафик.

## Проверка после деплоя

```bash
cd /var/www/stroyka-app
read -s PASS
SMOKE_EMAIL='admin@stroyka.ru' SMOKE_PASSWORD="$PASS" npm run smoke:prod
npm run smoke:public-api
npm run smoke:public-site
curl -sS -o /tmp/stroyka-estimate-reconciliations.out -w 'estimate-reconciliations HTTP=%{http_code}\n' https://stroyka26.pro/estimate-reconciliations
curl -sSI https://stroyka26.pro/ | head -20
curl -sS https://stroyka26.pro/sitemap.xml | head -20
curl -sS https://stroyka26.pro/llms.txt | head -40
curl -sSI https://stroyka26.pro/features.html | head -10
curl -sSI https://stroyka26.pro/project-catalog.html | head -10
curl -sS https://stroyka26.pro/project-catalog.json | head -40
curl -sSI 'https://stroyka26.pro/?project=H1-01#projects' | head -10
curl -sSI https://stroyka26.pro/contacts.html | head -10
curl -sSI https://stroyka26.pro/privacy.html | head -10
curl -sSI https://stroyka26.pro/terms.html | head -10
```

## Деплой

```bash
cd /var/www/stroyka-app && git pull --ff-only && PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py && npm run build && npm run smoke:public-site && bash deploy.sh
```

Если добавлены новые backend routes, сначала обновить nginx routes и проверить, что они не отдают React `index.html`:

```bash
nginx -t && systemctl reload nginx
npm run smoke:public-api
```
