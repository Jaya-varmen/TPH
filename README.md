# TPH Telegram Bot

Telegram-бот для расчета метрик по видео по запросам на русском языке.

## Что делает проект

- Загружает `videos.json` в PostgreSQL в нормализованные таблицы `videos` и `video_snapshots`.
- Принимает текстовый запрос в Telegram.
- Преобразует запрос в `QueryPlan` (правила + LLM fallback).
- Строит SQL и возвращает одно число.

## Стек

- Python 3.11
- aiogram 3 (асинхронный бот)
- SQLAlchemy 2 + asyncpg (асинхронная БД)
- PostgreSQL 15
- Docker Compose
- GigaChat API (опционально, как fallback парсинга)

## Структура проекта

- `app/bot.py` - Telegram-бот и обработчик сообщений
- `app/nlp.py` - rule-based разбор естественного языка в `QueryPlan`
- `app/llm.py` - fallback разбор через GigaChat
- `app/query_builder.py` - преобразование `QueryPlan` в SQLAlchemy Select
- `app/load_data.py` - загрузка JSON в БД
- `app/migrate.py` - применение SQL-миграций
- `migrations/001_init.sql` - создание таблиц и индексов
- `scripts/entrypoint.sh` - пайплайн запуска контейнера

## Подготовка окружения

### 1. Создайте `.env`

```bash
cp .env.example .env
```

Минимально обязательные переменные:

- `BOT_TOKEN`
- `GIGACHAT_AUTH_KEY` (если `LLM_ENABLED=true`)

### 2. Где получить ключи

#### `BOT_TOKEN`

1. Откройте [@BotFather](https://t.me/BotFather).
2. Выполните `/newbot`.
3. Полученный токен вставьте в `BOT_TOKEN`.

#### `GIGACHAT_AUTH_KEY`

1. Откройте [GigaChat Studio](https://developers.sber.ru/studio/).
2. Создайте проект.
3. В настройках API сгенерируйте `Authorization Key`.
4. Вставьте его в `GIGACHAT_AUTH_KEY`.

Документация:

- [GigaChat API Overview](https://developers.sber.ru/docs/ru/gigachat/api/overview)
- [Quickstart API](https://developers.sber.ru/docs/ru/gigachat/quickstart/ind-using-api)

## Запуск

```bash
docker compose up --build
```

При старте контейнера:

1. Ожидание готовности PostgreSQL.
2. Применение миграций.
3. Загрузка данных из `data/videos.json` (идемпотентно, только если таблицы пустые).
4. Запуск Telegram-бота.

## Полезные команды

Остановить:

```bash
docker compose down
```

Запуск в фоне:

```bash
docker compose up -d --build
```

Логи бота:

```bash
docker compose logs -f bot
```

## Как NL-запрос превращается в SQL

1. `app/nlp.py` извлекает:
- метрику (`views`, `likes`, `comments`, `reports`);
- тип агрегации (`count`/`sum`);
- диапазон дат;
- `creator_id`;
- порог (`>`, `>=`, `<`, `<=`);
- специальные условия (например, "первые N часов после публикации").

2. Результат описывается структурой `QueryPlan`.

3. `app/query_builder.py` собирает SQLAlchemy-запрос:
- выбирает таблицу (`videos` или `video_snapshots`);
- применяет фильтры;
- считает `sum` или `count` (включая `count(distinct video_id)` где нужно).

4. `app/db.py` выполняет запрос и бот возвращает одно число.

## LLM fallback (GigaChat)

Если rule-based парсер не распознал запрос и включен `LLM_ENABLED=true`, используется `app/llm.py`.

Подход:

- LLM получает описание схемы.
- LLM обязана вернуть строго JSON с полями `QueryPlan`.
- JSON валидируется перед построением SQL.

Базовый формат ответа LLM:

```json
{
  "source": "videos | snapshots",
  "aggregate": "count | sum",
  "metric": "videos | views | likes | comments | reports",
  "use_delta": true,
  "distinct": false,
  "date_from": "YYYY-MM-DD or null",
  "date_to": "YYYY-MM-DD or null",
  "hours_after_publication": "number or null",
  "creator_id": "string or null",
  "threshold": {"metric": "views", "op": ">", "value": 1000},
  "positive_only": false
}
```

## Проверка через служебного бота

После запуска вашего бота в Telegram отправьте в `@PPS_Check_bot`:

```text
/check @yourbotnickname https://github.com/yourrepo Фамилия
```

Условия успешной проверки:

- бот должен быть запущен и доступен в Telegram;
- репозиторий должен быть публичным;
- в репозитории должны быть исходники, миграции, загрузка данных и README.
