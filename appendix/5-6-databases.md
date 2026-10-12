# Приложение 5–6. Базы данных: объемы, запросы, кеш и размещение

К основной части: [раздел 5](../README.md#5-логическая-схема-бд), [раздел 6](../README.md#6-физическая-схема-бд). Номера «п. X.Y» — пункты основной части.

## Кеши, счетчики и буферы

Это производные данные: на картинке их нет, но они хранятся и нагружают хранилища.

| Сущность | Тип данных | Что хранит | Ключ | Связь |
| -------- | ---------- | ---------- | ---- | ----- |
| `meetings_runtime` | hot state | Онлайн-состояние идущей встречи: статус, число участников онлайн, пул SFU, время последнего heartbeat | `meeting_id` | 1:1 к `meetings` |
| `chat_seq` | счетчик | Последний выданный номер сообщения в чате встречи | `meeting_id` | 1:1 к `meetings` |
| `chat_dedup` | ключ идемпотентности | Принятые `client_msg_id` за последние 60 с и выданный им `message_seq` | `meeting_id + client_msg_id` | N:1 к `meetings` |
| `active_invite_tokens` | кеш | Токены приглашений за последние сутки | `token` | кеш `meeting_invite_links` |
| `chat_last100` | буфер в памяти | Последние 100 сообщений идущей встречи | `meeting_id` | кеш `chat_messages` |

## Размеры данных и QPS: как посчитано

Кроме допущений из приложения 2: одна активная сессия на DAU, она создается при логине. Сессия проверяется при `create`, `join`, открытии списка встреч и записи. Трафик внутри встречи (`leave`, чат, WS, медиа) авторизуется подписанным `join_token` в `home_dc` без похода в `user_sessions`. На встречу — одна ссылка-приглашение; запись хранит видео, аудио и текст чата [^7].

| Таблица | Строки / окно | Байт / строка | Объем | Read QPS peak | Write QPS peak | Основание |
| ------- | :-----------: | ------------: | ----: | ------------: | -------------: | --------- |
| `users` | 320 000 000 | 256 B | 81.92 GB | 7 726 | ≤ 1 997 | Чтение при `login`, `create`, `join`; запись — регистрации и профиль, верхняя оценка — каждый DAU раз в сутки (п. 3.4) |
| `user_sessions` | 115 000 000 | 128 B | 14.72 GB | 12 240 | 1 997 | Проверка при `create`, `join`, `list` и открытии записи; запись при `login` |
| `meetings` | 900 000 000 / 30 дней | 256 B | 230.4 GB | 10 938 | 521 | Чтение при `join`, `leave`, метаданных записи; запись при `create` |
| `meeting_participants` | 9 000 000 000 / 30 дней | 128 B | 1.152 TB | 5 208 | 10 417 | `join + leave` |
| `meeting_invite_links` | 900 000 000 / 30 дней | 128 B | 115.2 GB | 5 208 | 521 | Одна ссылка на встречу |
| `user_meetings` | 9 000 000 000 / 30 дней | 128 B | 1.152 TB, копия в каждом ДЦ | 5 990 запросов, по 100 строк | 10 938 | Строка организатора при `create`, участника при `join`, статус при `leave` |
| `chat_messages` | 45 000 000 000 / 30 дней | 1 KB в среднем, до 10 KB | 45 TB | ≤ 5 208 запросов по 100 строк, только промахи буфера | 26 042 | Новые сообщения доставляются через WS без чтения из БД |
| `recordings` | 900 000 000 / 30 дней | 256 B + файл | 230.4 GB метаданных + 685.26 PB файлов | ≤ 521 | 521 | Метаданные пишутся в конце встречи, открытие — не больше одного на запись |
| `recording_upload_buffer` | ≈ 80 млн частей в пик | 8 MB | ≈ 642 TB в пик, входит в 685.26 PB | — | 49 570 PUT/с | 3 172.5 Гбит/с / 8 MB. Части не читаются: S3 сам собирает из них объект |

### Кеши и счетчики

| Сущность | Записи / окно | Байт / запись | Объем | Read QPS peak | Write QPS peak | Основание |
| -------- | :-----------: | ------------: | ----: | ------------: | -------------: | --------- |
| `meetings_runtime` | 1 687 500 в пик | 512 B | 0.864 GB | — | 685 938 | heartbeat 675 000 + `join`/`leave` 10 417 + `create` 521 |
| `chat_seq` | 1 687 500 в пик | один счетчик на встречу | входит в `meetings_runtime` | — | 26 042 `INCR` | один номер на сообщение |
| `chat_dedup` | ≈ 1.56 млн ключей в пик | ≈ 100 B | ≈ 0.16 GB | — | 26 042 `SET NX` | ключ живет 60 с: 26 042 × 60 |
| `active_invite_tokens` | 30 000 000 | 128 B | 3.84 GB | 5 208 | 521 | токены встреч за сутки |
| `chat_last100` | 168.75 млн сообщений в пик | 1 KB | 168.75 GB | ≤ 5 208 запросов по 100 строк | 26 042 | 1 687 500 встреч × 100 сообщений |

## Где хранятся данные

| Таблица | Где хранится | Главный ключ доступа | Размещение по ДЦ (п. 3.4) |
| ------- | ------------ | -------------------- | ------------------------- |
| `users` | PostgreSQL, `auth_pg` | `id`, `email` | primary в `DC-US-EAST`, реплики во всех ДЦ |
| `user_sessions` | Redis Cluster, `session_redis` | `session_id` = `<dc>.<128 бит>` | ДЦ логина, перенос по запросу |
| `meetings` | PostgreSQL + Citus, `meeting_pg` | `id = meeting_id` | `home_dc` + реплика в парном ДЦ |
| `meeting_participants` | ScyllaDB, `meeting_scylla` | `meeting_id + bucket + user_id` | `home_dc` |
| `meeting_invite_links` | PostgreSQL + Citus, `meeting_pg` | `token_hash`, `token` | `home_dc` + реплика в парном ДЦ |
| `user_meetings` | ScyllaDB, `meeting_scylla` | `user_id + scheduled_start` | все ДЦ, RF=3 в каждом |
| `meetings_runtime` | Redis Cluster, `runtime_redis` | `meeting_id` | `home_dc` |
| `chat_messages` | ScyllaDB, `chat_scylla` | `meeting_id + bucket + message_seq` | `home_dc` |
| `recordings` | PostgreSQL + Citus, `recording_pg` | `meeting_id`, `id` | `home_dc` + реплика в парном ДЦ |
| `recording_upload_buffer` | S3-compatible Object Storage | `recording_id + chunk_number` | `home_dc` |
| `chat_seq`, `chat_dedup`, `active_invite_tokens` | Redis Cluster, `runtime_redis` | `meeting_id`, `token` | `home_dc` |
| `chat_last100` | Память Chat-сервиса | `meeting_id` | `home_dc` |

`meeting_pg` и `recording_pg` — две схемы одной базы на Citus-кластере ДЦ: co-location работает только внутри одной базы. У `meetings` и `recordings` одна колонка распределения — `meeting_id`, поэтому шарды встречи и ее записей лежат на одном узле [^30].

## Индексы: пояснения

- Индекс в шардированной таблице работает внутри шарда, поэтому запрос сначала должен попасть в нужный шард по `meeting_id`, `user_id` или `token_hash`.
- `meeting_invite_links`: колонка распределения — `token_hash = hash(token)`, и в Citus PK и UNIQUE обязаны ее включать [^94]. `token_hash` вычисляется из `token`, поэтому `UNIQUE(token_hash, token)` — та же уникальность токена.
- `chat_dedup`: в ScyllaDB нет UNIQUE — `INSERT` с тем же ключом перезаписывает строку [^101], а повтор получил бы новый `message_seq`, то есть другой ключ, — дубль. Поэтому идемпотентность держит Redis: повтор с тем же `client_msg_id` получает уже выданный номер [^45].
- `meetings_runtime`: вторичных индексов в Redis нет, поэтому поиск «по времени последнего heartbeat» не нужен — брошенную встречу удаляет TTL [^22].

## Шардирование: почему такие ключи

| Таблица | Шардируем | Почему |
| ------- | --------- | ------ |
| `users` | Нет на MVP | 81.92 GB, записей мало; один primary на весь мир (п. 3.4) |
| `user_sessions` | Да | 115 млн активных сессий, кластер в каждом ДЦ |
| `meetings` | Да: по `home_dc`, затем по `meeting_id` | 900 млн строк за 30 дней; в самом большом ДЦ ≈ 321 млн |
| `meeting_participants` | Да | 9 млрд строк за 30 дней |
| `meeting_invite_links` | Да | `join` начинается с токена |
| `user_meetings` | Да | Свой список пользователь читает без fan-out |
| `meetings_runtime` | Да | ≈ 0.74 млн ops/s на весь мир вместе с `chat_seq` и `chat_dedup` |
| `chat_messages` | Да | Чат читается по встрече и диапазону `seq` |
| `recordings` | Да | Записи читаются по встрече |
| `recording_upload_buffer` | Да | Части собираются в одну запись |

Метаданных в одном ДЦ немного: в самом большом, `DC-DE-FRANKFURT`, ≈ 206 GB и ≈ 5 950 чтений/с. Поэтому Citus в каждом ДЦ работает в режиме single-node — координатор сам хранит шарды [^90]. Колонка распределения `meeting_id` задана сразу: при росте добавляются worker-узлы с ребалансировкой шардов без смены схемы [^29][^30].

Репликация масштабирует чтение, шардирование — запись. JOIN на горячем пути нет: таблицы разных СУБД связаны логически, без физических FK, а каждый запрос идет по ключу шарда (п. 6.5).

## Нагрузка на строки

| API / событие | Peak RPS | Что трогаем | Строк / ключей на запрос | Строк в секунду |
| ------------- | -------: | ----------- | ------------------------: | --------------: |
| `POST /auth/login` | **1 997** | `users` (чтение реплики), `user_sessions` (запись) | 2 | **3 993** |
| `POST /meetings` | **521** | `meetings`, `meeting_invite_links`, `user_meetings`, `meetings_runtime` | 4 | **2 083** |
| `POST /meetings/{id}/join` | **5 208** | `user_sessions`, `meeting_invite_links`, `meetings`, `meeting_participants`, `user_meetings`, `meetings_runtime` | 6 | **31 250** |
| `POST /meetings/{id}/leave` | **5 208** | `meeting_participants`, `user_meetings`, `meetings_runtime` | 3 | **15 625** |
| `WS /presence/heartbeat` | **675 000** | `meetings_runtime` | 1 | **675 000** |
| `POST /meeting-chat/messages` | **26 042** | `chat_dedup` и `chat_seq` (один скрипт Redis), `chat_messages` | 3 | **78 125** |
| `GET /meeting-chat/messages?after_seq=N` | **5 208** | `chat_last100` в памяти; `chat_messages` в ScyllaDB — только при промахе | 100 | **520 833** |
| `GET /users/{id}/meetings?limit=100` | **5 990** | `user_meetings` | 100 | **598 958** |
| `POST /recordings/metadata` | **521** | `recordings`, `meetings` | 2 | **1 042** |
| `GET /recordings/{id}` | **521** | `user_sessions`, `recordings` | 2 | **1 042** |

История чата читается из буфера комнаты в памяти Chat-сервиса (раздел «Кеш» ниже): 520 833 строк/с — это память, в ScyllaDB идут только промахи. Heartbeat трогает только `meetings_runtime`: WSS-соединение авторизуется один раз при подключении по `join_token`, поэтому `user_sessions` на каждом heartbeat не читается.

## API → запрос → БД

| API | Запросы к БД | Где выполняется |
| --- | ------------ | --------------- |
| `POST /meetings` | `INSERT INTO meetings`, `INSERT INTO meeting_invite_links`; `INSERT INTO user_meetings` — строка организатора; `HSET runtime:{meeting_id}` | Citus; ScyllaDB; Redis |
| `POST /meetings/{id}/join` | `GET session:{session_id}` (если сессии нет локально — один gRPC-запрос в ДЦ из префикса, сценарий в приложении 3); `SELECT meeting_id FROM meeting_invite_links WHERE token_hash = hash(?) AND token = ?`; `SELECT id, status, home_dc FROM meetings WHERE id = ?`; `INSERT INTO meeting_participants`, `INSERT INTO user_meetings`; `HINCRBY runtime:{meeting_id} participants_online_count 1` | Redis; Citus; ScyllaDB; Redis |
| `POST /meetings/{id}/leave` | `UPDATE meeting_participants`, `UPDATE user_meetings SET status`; `HINCRBY runtime:{meeting_id} participants_online_count -1` | ScyllaDB; Redis |
| `WS /presence/heartbeat` | `HSET runtime:{meeting_id} updated_at` и продление TTL | Redis |
| `POST /meeting-chat/messages` | Скрипт: `SET chat_dedup:{meeting_id}:{client_msg_id} NX EX 60`, при успехе `INCR chat_seq:{meeting_id}`; `INSERT INTO chat_messages` | Redis, один слот; ScyllaDB |
| `GET /meeting-chat/messages?after_seq=N` | Из буфера комнаты; при промахе `SELECT ... WHERE meeting_id=? AND bucket=? AND message_seq>? LIMIT 100` | Память Chat-сервиса / ScyllaDB |
| `GET /users/{id}/meetings?limit=100` | `SELECT ... WHERE user_id=? LIMIT 100` | ScyllaDB |
| `POST /recordings/metadata` | Чтение `meetings` по `id`; `INSERT INTO recordings` | Citus |
| `GET /recordings/{id}` | `GET session:{session_id}`; `SELECT storage_bucket, storage_key FROM recordings WHERE meeting_id = ? AND id = ?` и выдача presigned URL | Redis; Citus |
| Воркер записи | `UploadPart`: часть `n` multipart upload, 8 MB | S3 |

Запросы к таблицам встречи выполняются в `home_dc`: если `join` пришел в другой ДЦ, control plane проксирует его туда по коду ДЦ в `meeting_id` (п. 3.4).

## Кеш

| Кеш | Объем | Пиковые операции | Как посчитано | Решение |
| --- | ----: | ---------------: | ------------- | ------- |
| `meetings_runtime` | **0.864 GB** | **685 938 ops/s** | 1 687 500 встреч × 512 B; heartbeat 675 000 + join 5 208 + leave 5 208 + create 521 | Redis `runtime_redis` |
| `chat_seq` + `chat_dedup` | **≈ 0.16 GB** | **52 083 ops/s** | `INCR` 26 042 + `SET NX` 26 042; ключи живут 60 с: ≈ 1.56 млн × 100 B | Тот же `runtime_redis` (всего 738 021 ops/s), ключи встречи в одном слоте |
| `user_sessions` | **14.72 GB** | **14 236 ops/s** | Проверки при create, join, list и открытии записи (12 240) + логины (1 997) | Redis `session_redis` |
| `active_invite_tokens` | **3.84 GB** | **5 208 ops/s** | 30 000 000 встреч в сутки × 128 B | Redis, источник правды — PostgreSQL |
| `user_meetings_top100` | **1.472 TB** | **598 958 строк/с** | 115 000 000 DAU × 100 × 128 B | Не кешируем целиком: read model в ScyllaDB |
| `chat_last100` | **168.75 GB** | **≤ 520 833 строк/с** чтения, 26 042 записей/с | 1 687 500 встреч × 100 × 1 KB | Буфер комнаты в памяти Chat-сервиса, не общий Redis |

## Денормализация: горячие сценарии

Каждый горячий сценарий читает одну таблицу по одному ключу: свои встречи — `user_meetings` по `user_id`; события и участники встречи — по `meeting_id`; новые сообщения — `chat_messages` по `meeting_id + bucket + message_seq`.

## Резервное копирование: объем бэкапов

Бэкапы баз — сотни терабайт, доли процента от 685 PB записей: на стоимость (п. 11.2) они не влияют.

## Источники

[^7]: [Zoom Support — Starting a cloud recording](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0062627)

[^22]: [Redis Docs — Key expiration](https://redis.io/docs/latest/develop/using-commands/keyspace/)

[^29]: [Citus Documentation — Choosing Distribution Column](https://docs.citusdata.com/en/stable/sharding/data_modeling.html)

[^30]: [Citus Documentation — Table Co-Location](https://docs.citusdata.com/en/stable/sharding/data_modeling.html#table-co-location)

[^45]: [Stripe Docs — Idempotent requests](https://docs.stripe.com/api/idempotent_requests)

[^90]: [Citus Documentation — Single-Node Citus](https://docs.citusdata.com/en/stable/installation/single_node.html)

[^94]: [Citus Documentation — Creating and Modifying Distributed Objects (DDL): первичные ключи и UNIQUE должны включать колонку распределения](https://docs.citusdata.com/en/stable/develop/reference_ddl.html)

[^101]: [ScyllaDB Documentation — CQL INSERT: в отличие от SQL, INSERT не проверяет, существует ли строка](https://docs.scylladb.com/manual/stable/cql/dml/insert.html)
