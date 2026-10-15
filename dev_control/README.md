# Stroyka Dev Control — Jev / Timeweb adapter

Первый изолированный слой будущего браузерного QA-контура.

## Что делает этот этап

- обращается к Timeweb AI Gateway SystemOne;
- использует модель `jev-latest`;
- получает ключ только из переменной окружения `TIMEWEB_AI_API_KEY`;
- не подключается к production БД;
- не запускает браузер;
- не выполняет deploy или migrations;
- не хранит секреты в GitHub.

Endpoint по умолчанию:

```
https://api.timeweb.ai/v1/systemone
```

## Переменные окружения

Обязательная:

```
TIMEWEB_AI_API_KEY
```

Необязательные:

```
JEV_SYSTEMONE_URL=https://api.timeweb.ai/v1/systemone
JEV_MODEL=jev-latest
```

## Unit tests

Тесты не ходят в интернет и не требуют ключа:

```bash
python -m unittest dev_control.test_jev_timeweb -v
```

## Ручная проверка соединения

После того как ключ добавлен в переменные окружения Timeweb:

```bash
python -m dev_control.jev_timeweb --smoke-test
```

Это отправляет один безвредный классификационный запрос и выводит только поле
`answers`. Ключ не печатается.

## Следующий этап

После подтверждённого smoke-test отдельным PR подключить браузерный worker:

```
Work Control
  -> QA task
  -> Browser worker / Chrome
  -> Jev decision
  -> deterministic verifier
  -> evidence (steps/screenshots)
  -> GitHub Issue/PR status
```

Jev не определяет финальный статус "готово": результат должен подтверждаться
детерминированным verifier и существующим контуром #66.
