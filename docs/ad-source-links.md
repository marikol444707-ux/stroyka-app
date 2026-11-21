# Ссылки для рекламы в Telegram

Каждая ссылка ведёт на сайт СтройКа и запоминает, из какого канала пришёл человек. Это запоминание держится 30 дней, даже если человек потом открывает другие страницы сайта и только после этого оставляет заявку.

В заявке источник будет написан понятно, например: «Сайт / Нетипичный Ставрополь».

| Канал | Ссылка |
| --- | --- |
| Нетипичный Ставрополь | https://stroyka26.pro/?utm_source=netip&utm_medium=telegram&utm_campaign=ads |
| Блокнот | https://stroyka26.pro/?utm_source=bloknot&utm_medium=telegram&utm_campaign=ads |
| s1777 | https://stroyka26.pro/?utm_source=s1777&utm_medium=telegram&utm_campaign=ads |
| minvody | https://stroyka26.pro/?utm_source=minvody&utm_medium=telegram&utm_campaign=ads |
| ptgorsk | https://stroyka26.pro/?utm_source=ptgorsk&utm_medium=telegram&utm_campaign=ads |
| novoalex | https://stroyka26.pro/?utm_source=novoalex&utm_medium=telegram&utm_campaign=ads |
| barahkmv | https://stroyka26.pro/?utm_source=barahkmv&utm_medium=telegram&utm_campaign=ads |
| izhs | https://stroyka26.pro/?utm_source=izhs&utm_medium=telegram&utm_campaign=ads |
| ipoteka | https://stroyka26.pro/?utm_source=ipoteka&utm_medium=telegram&utm_campaign=ads |
| pyatigorsk_rab | https://stroyka26.pro/?utm_source=pyatigorsk_rab&utm_medium=telegram&utm_campaign=ads |

Код канала в ссылке (`utm_source`) должен совпадать с таблицей. Человеческие названия задаются в одном месте: `backend/features/crm/ad_sources.py`. Если код ещё без названия, в заявке будет виден сам код.

Как владельцу приходит сообщение о новой заявке, написано в `docs/lead-owner-notifications.md`.
