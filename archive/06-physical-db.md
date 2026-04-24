# 06. Физическая схема БД — расширенное обоснование

## Физические проекции данных

| Проекция | Ключ доступа | Какие сценарии обслуживает | Принцип |
|---|---|---|---|
| Room-centric | `room_id` | send/history/fan-out, voice room state | все горячие данные комнаты физически рядом |
| User-centric | `user_id` | session/presence/user feed | операции пользователя без scatter-gather |
| Time-centric | `event_time` | аналитика и отчеты | дешевые range-сканы по времени |

## Выбор хранилищ по таблицам

| Физический объект | Хранилище | Ключ/индексы | Репликация | Причина выбора |
|---|---|---|---|---|
| `users` | PostgreSQL | PK `id`, unique `email`, `phone` | 1 primary + 2 standby | строгая консистентность и уникальность |
| `servers`, `rooms` | PostgreSQL/Citus | PK `id`, idx `owner_id`, `server_id` | RF=2 на distributed tables | scale-out при сохранении SQL-модели |
| `sessions` | Redis | key `session:{token}` + TTL | primary + replica + sentinel | very low-latency lookup |
| `room_participants` | Redis/Aerospike | key `room:{id}:participants` | RF=3 | экстремально горячий runtime-state |
| `messages` | ScyllaDB/Aerospike | PK `(room_id, ts_bucket, msg_id)` | RF=3 | high write throughput и быстрый history read |
| `message_reactions` | ScyllaDB | PK `(room_id, msg_id, user_id)` | RF=3 | локальность по сообщению |
| `presence` | Redis Cluster | key `presence:{user_id}:{device_id}` | primary + replicas | эфемерное состояние, TTL |
| `analytics_events` | Kafka -> ClickHouse | partition by time/event | ReplicatedMergeTree | дешевые агрегации и ретеншн |
| `recordings` binary | S3-compatible | object key | multi-AZ | дешево и масштабно для BLOB |
| `recordings` metadata | PostgreSQL/Citus | PK `id`, idx `room_id, created_at` | RF=2 | транзакционные метаданные |

## Индексы (критичные)

| Объект | Индекс / ключ | Тип | Для чего нужен |
|---|---|---|---|
| `users` | `uq_users_email` | UNIQUE | login by email |
| `users` | `uq_users_phone` | UNIQUE | login by phone |
| `rooms` | `idx_rooms_server_id` | BTREE | список комнат сообщества |
| `rooms` | `idx_rooms_updated_at` | BTREE | сортировка активных комнат |
| `messages` | `(room_id, ts_bucket, msg_id)` | PARTITION KEY | append + paginated history |
| `message_reactions` | `(room_id, msg_id, user_id)` | COMPOSITE KEY | идемпотентные реакции |
| `recordings` | `idx_recordings_room_created` | BTREE | список записей комнаты |
| `analytics_events` | `ORDER BY (event_time, event_type, room_id)` | ClickHouse sort key | быстрые временные выборки |

## Шардирование

| Сущность | Ключ шардирования | Алгоритм | Почему |
|---|---|---|---|
| `messages` | `room_id` | rendezvous/hash | room-local read/write без cross-shard |
| `message_reactions` | `room_id` | hash(room_id) | рядом с сообщениями комнаты |
| `room_participants` | `room_id` | hash(room_id) | быстрые join/leave updates |
| `sessions` | `token` | hash(token) | равномерный key-space |
| `presence` | `user_id` | hash(user_id) | user-centric доступ |
| `analytics_events` | `event_time` | time partition + hash | быстрый ingest и range scan |

## Репликация и отказоустойчивость

| Контур | Схема | Цель |
|---|---|---|
| PostgreSQL | synchronous/asynchronous replicas + failover manager | защита auth/identity path |
| Scylla/Aerospike | RF=3, quorum reads/writes | устойчивость hot message path |
| Redis | primary/replica + sentinel/cluster failover | быстрый recovery stateful cache |
| ClickHouse | ReplicatedMergeTree + distributed tables | отказ узла без потери аналитики |
| S3 | multi-AZ replication + versioning | durability записей и файлов |

## Backup и восстановление

| Хранилище | Политика backup | Частота | RPO/RTO ориентир |
|---|---|---|---|
| PostgreSQL | full + WAL | daily + continuous WAL | RPO < 5 min, RTO < 30 min |
| Scylla/Aerospike | incremental snapshot | каждые 6-12 часов | RPO < 30 min, RTO < 60 min |
| Redis | AOF + periodic RDB | continuous + hourly | RPO < 1 min |
| ClickHouse | partition backup to S3 | hourly/daily | RPO < 15 min |
| S3 | versioning + lifecycle + replication | continuous | platform-level durability |

## Карта API -> хранилища

| API-вызов | Основные объекты | Что происходит |
|---|---|---|
| `POST /rooms/{id}/join` | `rooms`, `room_participants`, `sessions` | ACL-check, запись runtime-state, обновление presence |
| `POST /messages/send` | `messages`, `message_reactions` | append message + async fan-out event |
| `GET /messages/history` | `messages` | range-read по `(room_id, ts_bucket)` |
| `POST /auth/validate` | `sessions`, `users` | проверка токена и статуса пользователя |
| `GET /recordings` | `recordings` metadata + S3 | список и presigned URLs |
| `POST /events` | `analytics_events` | async запись через Kafka |

## Узкие места и как закрываем

| Риск | Где возникает | Механизм снижения |
|---|---|---|
| hot room partition | `messages`, `room_participants` | room splitting, adaptive routing, rate limits |
| reconnect storm | `sessions`, `presence` | jittered backoff + token cache |
| write burst analytics | `analytics_events` | Kafka buffer + batched inserts |
| large history scans | `messages` | time buckets + keyset pagination |
