# TPH Telegram Bot

Telegram-бот для расчета метрик по видео из PostgreSQL на основе запросов на русском языке.

## Требования

- Docker Desktop (или Docker Engine + Docker Compose)
- Доступ в интернет для Telegram API и GigaChat API

## 1. Подготовка `.env`

В корне проекта создайте файл `.env` из шаблона:

```bash
cp .env.example .env
```

Заполните в `.env` эти переменные:

- `BOT_TOKEN`
- `GIGACHAT_AUTH_KEY`

Остальные значения можно оставить как в `.env.example`.

## 2. Где получить ключи

### `BOT_TOKEN` (Telegram)

1. Откройте бота [@BotFather](https://t.me/BotFather) в Telegram.
2. Выполните `/newbot` и создайте бота.
3. BotFather выдаст токен, вставьте его в `BOT_TOKEN` в `.env`.

### `GIGACHAT_AUTH_KEY` (Sber GigaChat API)

1. Войдите в [GigaChat Studio](https://developers.sber.ru/studio/).
2. Создайте проект (или откройте существующий).
3. В разделе настроек API сгенерируйте `Authorization Key`.
4. Вставьте его в `GIGACHAT_AUTH_KEY` в `.env`.

Документация:
- [GigaChat API Overview](https://developers.sber.ru/docs/ru/gigachat/api/overview)
- [Quickstart (получение токена и вызовы API)](https://developers.sber.ru/docs/ru/gigachat/quickstart/ind-using-api)

## 3. Запуск проекта

Собрать и запустить:

```bash
docker compose up --build
```

Что произойдет при старте:

- поднимется контейнер PostgreSQL;
- применятся SQL-миграции;
- загрузится `data/videos.json` в БД (если таблицы пустые);
- запустится Telegram-бот.

## 4. Проверка, что бот запущен

Откройте своего бота в Telegram и отправьте тестовый запрос, например:

`Сколько всего видео есть в системе?`

Бот должен вернуть одно число.

## 5. Полезные команды

Остановить контейнеры:

```bash
docker compose down
```

Запуск в фоне:

```bash
docker compose up -d --build
```

Просмотр логов:

```bash
docker compose logs -f bot
```
