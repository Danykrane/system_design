# 06. Физическая схема БД — rationale

## Выбор хранилищ по нагрузке

| Зона данных | Хранилище | Причина |
|---|---|---|
| ACID core (`users`, `sessions`, billing-like metadata) | PostgreSQL | транзакции, индексы, строгая консистентность |
| Hot message path | ScyllaDB/Aerospike | высокий write throughput и горизонтальное масштабирование |
| Cache/session/presence | Redis | минимальная latency и TTL-модель |
| Analytics/events | ClickHouse | дешевые агрегации по большим объемам |
| Binary objects (`recordings`, avatars) | S3-compatible object storage | low-cost scale-out хранение |

## Паттерн ключей и шардирования

| Таблица/поток | Шард-ключ | Примечание |
|---|---|---|
| `messages` | `room_id` | локальность данных комнаты |
| `room_participants` | `room_id` | быстрый fan-out по комнате |
| `presence` | `user_id` | равномерный key-space |
| `analytics_events` | `event_time` + `event_type` | партиционирование по времени |
