# Telegram-бот для подсчета метрик по видео

Бот отвечает на запросы на русском естественном языке и возвращает одно число (count/sum/прирост), используя данные из PostgreSQL.

## Стек
- Python 3.11 + `aiogram` (асинхронный бот)
- PostgreSQL
- `SQLAlchemy` (async) + `asyncpg`
- Docker Compose (запуск одной командой)
- Опционально LLM (GigaChat) для разбора сложных запросов

## Быстрый старт (Docker Compose)
1. Скопируйте `.env.example` в `.env` и заполните значения:
   - `BOT_TOKEN` — токен Telegram-бота (BotFather)
   - `GIGACHAT_AUTH_KEY` — Authorization Key из GigaChat API (если включен LLM)

2. Запуск:
```bash
docker compose up --build
```

После запуска:
- база данных создается автоматически;
- таблицы создаются из `migrations/001_init.sql`;
- данные из `data/videos.json` загружаются один раз;
- бот начинает polling.

## Где получить ключ GigaChat
1. Зарегистрируйтесь в [GigaChat API](https://developers.sber.ru/docs/ru/gigachat/api/overview) и перейдите в [GigaChat Studio](https://developers.sber.ru/studio/).
2. Создайте проект и откройте его раздел `Настройки API`.
3. Сгенерируйте `Authorization Key`.
4. Укажите его в `.env` как `GIGACHAT_AUTH_KEY`.

Примечание: по документации сначала берется `Authorization Key`, потом бот автоматически получает `access_token` через `POST /api/v2/oauth` и использует его для `POST /api/v1/chat/completions`.

## Переменные окружения
- `BOT_TOKEN` — обязателен
- `DATABASE_URL` — по умолчанию `postgresql+asyncpg://app:app@db:5432/app`
- `DATA_JSON_PATH` — по умолчанию `/app/data/videos.json`
- `LLM_ENABLED` — `true/false` (по умолчанию `true`)
- `GIGACHAT_AUTH_KEY` — Authorization Key из Studio
- `GIGACHAT_SCOPE` — по умолчанию `GIGACHAT_API_PERS`
- `GIGACHAT_MODEL` — по умолчанию `GigaChat-2`
- `GIGACHAT_OAUTH_URL` — по умолчанию `https://ngw.devices.sberbank.ru:9443/api/v2/oauth`
- `GIGACHAT_API_BASE_URL` — по умолчанию `https://gigachat.devices.sberbank.ru/api/v1`
- `GIGACHAT_VERIFY_SSL` — по умолчанию `true`

## Примеры запросов
- «Сколько всего видео есть в системе?»
- «Сколько видео у креатора с id ... вышло с 1 ноября 2025 по 5 ноября 2025 включительно?»
- «Сколько видео набрало больше 100 000 просмотров за всё время?»
- «На сколько просмотров в сумме выросли все видео 28 ноября 2025?»
- «Сколько разных видео получали новые просмотры 27 ноября 2025?»

## Архитектура
1. **Загрузка данных**
   - `migrations/001_init.sql` создает таблицы `videos` и `video_snapshots`.
   - `app/load_data.py` загружает `data/videos.json` в БД (идемпотентно).

2. **Парсинг запросов**
   - `app/nlp.py` — правило-ориентированный парсер (ключевые слова, даты, пороги, creator_id).
   - Если правила не сработали и включен LLM, используется `app/llm.py`.

3. **Query plan -> SQL**
   - `app/query_builder.py` строит безопасные SELECT-запросы (агрегации, фильтры по датам, creator_id, пороги).
   - Контекст диалога не хранится.

## Описание LLM-промпта (если включено)
LLM получает описание схемы и обязуется вернуть **строгий JSON** с планом запроса. Используется системный промпт:

```
Ты помощник, который преобразует запросы на русском в JSON план запроса к БД.

Схема БД:
- videos: id, creator_id, video_created_at, views_count, likes_count, comments_count, reports_count
- video_snapshots: id, video_id, views_count, likes_count, comments_count, reports_count,
  delta_views_count, delta_likes_count, delta_comments_count, delta_reports_count, created_at

Верни ТОЛЬКО JSON со следующими полями:
{
  "source": "videos" | "snapshots",
  "aggregate": "count" | "sum",
  "metric": "videos" | "views" | "likes" | "comments" | "reports",
  "use_delta": true | false,
  "distinct": true | false,
  "date_from": "YYYY-MM-DD" | null,
  "date_to": "YYYY-MM-DD" | null,
  "creator_id": "..." | null,
  "threshold": {"metric": "views|likes|comments|reports", "op": ">|>=|<|<=", "value": number} | null,
  "positive_only": true | false
}

Правила:
- Вопросы про публикацию видео ("вышло", "опубликовано") => source=videos, фильтр по video_created_at.
- Вопросы про прирост/рост/новые показатели за дату => source=snapshots, use_delta=true, фильтр по created_at.
- "Сколько видео" => aggregate=count, metric=videos.
- "Сколько просмотров/лайков/комментариев/жалоб" => aggregate=sum, metric=views|likes|comments|reports.
- "Сколько разных/уникальных видео" => distinct=true и metric=videos.
- Если указан creator id (32 hex), положи в creator_id.
- Если есть порог (больше/меньше N просмотров и т.п.), заполни threshold.
- Если запрос про новые просмотры, поставь positive_only=true.

Даты в формате "28 ноября 2025" приводи к ISO (YYYY-MM-DD). Если один день, date_from=date_to.
```

## Проверка
Перед отправкой в @PPS_Check_bot убедитесь, что бот запущен и доступен в Telegram.
