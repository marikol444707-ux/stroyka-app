# DDoS-защита и читаемость сайта для AI

План для `https://stroyka26.pro`.

## Главный принцип

Код приложения может ограничить спам, ботов и частые запросы, но настоящий DDoS нужно гасить до сервера: DNS/CDN/WAF, Nginx rate limit, firewall и мониторинг. Если атака дошла до Python-приложения, сервер уже тратит ресурсы.

## Что уже есть

- `/robots.txt` разрешает индексировать публичную главную страницу и закрывает приватные ERP-разделы.
- `/sitemap.xml` отдает публичный URL.
- `/sitemap.xml` включает статические публичные страницы `/features.html`, `/contacts.html`, `/privacy.html`, `/terms.html`.
- В `index.html` есть SEO, Open Graph и Twitter meta.
- В `index.html` добавлены JSON-LD данные `Organization`, `WebSite`, `SoftwareApplication`.
- `/llms.txt` дает AI-агентам короткое структурированное описание продукта.
- Статические публичные HTML-страницы дают поисковикам и AI-агентам читаемый текст без входа в ERP.
- `/login` защищен блокировкой после неудачных попыток.
- `/site/leads` фиксирует IP, User-Agent, referrer, UTM и имеет защиту от повторной заявки.
- Подготовлен `ops-nginx-stroyka-public-api.conf` для backend-маршрутов публичного сайта.
- `npm run smoke:public-api` проверяет, что публичные API не отдаются как React `index.html`.

## Что включить перед рекламой

1. Включить защиту на уровне провайдера или CDN/WAF.

   Минимальный вариант: защита от DDoS у хостинга/провайдера. Хороший вариант: CDN/WAF перед сервером, чтобы внешний трафик сначала проходил фильтр, а не сразу попадал на `147.45.237.127`.

2. Ограничить прямой доступ к origin-серверу.

   Если сайт стоит за CDN/WAF, Nginx должен принимать публичный трафик только от адресов CDN/WAF. Иначе атакующий сможет обойти CDN и бить напрямую по IP сервера.

3. Добавить Nginx rate limit.

   Пример нужно аккуратно совместить с текущим `/etc/nginx/sites-enabled/stroyka`, а не вставлять вслепую.

```nginx
# В http {} блоке nginx.conf
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=10r/m;
limit_req_zone $binary_remote_addr zone=lead_limit:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=workflow_limit:10m rate=30r/m;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

# В server {} сайта
limit_conn conn_limit 30;
client_max_body_size 25m;
client_body_timeout 15s;
keepalive_timeout 20s;

location = /login {
    limit_req zone=login_limit burst=10 nodelay;
    proxy_pass http://127.0.0.1:8001;
}

location = /site/leads {
    limit_req zone=lead_limit burst=5 nodelay;
    proxy_pass http://127.0.0.1:8001;
}

location = /site/pricing {
    limit_req zone=lead_limit burst=20 nodelay;
    proxy_pass http://127.0.0.1:8001;
}

location = /site/projects {
    limit_req zone=lead_limit burst=20 nodelay;
    proxy_pass http://127.0.0.1:8001;
}

location ^~ /site-price-rules {
    limit_req zone=login_limit burst=20 nodelay;
    proxy_pass http://127.0.0.1:8001;
}

location ~ ^/(workflow|telegram)/ {
    limit_req zone=workflow_limit burst=20 nodelay;
    proxy_pass http://127.0.0.1:8001;
}
```

После изменения:

```bash
nginx -t && systemctl reload nginx
npm run smoke:public-api
STRICT=1 npm run smoke:ops-prod
```

4. Для формы заявки добавить усиление, если начнется спам:

- скрытое honeypot-поле;
- задержка перед отправкой;
- captcha только при подозрительной активности;
- отдельный лимит по IP и телефону/email.

5. Для загрузок и workflow:

- оставить токены и авторизацию;
- ограничить размер файлов;
- хранить тяжелые файлы в S3;
- не запускать распознавание без явного действия пользователя.
- смотреть `/system-status`: там показываются ошибки API/frontend, локальные uploads и последний backup.

## Читаемость для AI и поиска

Сейчас сайт читаемый для AI-агентов на базовом уровне:

- `robots.txt` говорит, что можно читать;
- `sitemap.xml` показывает публичный URL;
- `llms.txt` объясняет продукт простым текстом;
- JSON-LD объясняет тип сайта и приложения;
- meta-теги дают описание для поисковиков и мессенджеров.

Ограничение: приложение на React рендерится на клиенте. Некоторые поисковые и AI-роботы читают такой сайт хуже, чем обычный статический HTML.

## Следующий уровень

Если нужен ещё более сильный SEO/AI-поиск, следующий шаг — SSR/prerender:

- `/` можно отдать как заранее сгенерированный HTML-лендинг с текстом, блоками, FAQ и формой заявки;
- ERP после входа остается React-приложением;
- приватные маршруты остаются закрытыми в `robots.txt`;
- sitemap уже расширен публичными HTML-страницами.

Это лучше, чем открывать рабочую ERP поисковикам.
