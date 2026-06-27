# Запуск публичного сайта

Короткий чеклист перед открытым запуском `https://stroyka26.pro`.

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
