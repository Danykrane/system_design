# Приложение 2. Расчет нагрузки: допущения и формулы

К основной части: [раздел 2](../README.md#2-расчет-нагрузки). Номера «п. X.Y» — пункты основной части.

## Исходные метрики и допущения

| Константа | Значение | Источник / основание |
| --------- | -------- | -------------------- |
| `MF_MAU` | 320 000 000 пользователей в месяц | Microsoft Teams, FY24 Q1 (2023); более новой публичной MAU-метрики нет [^1] |
| `MF_DAU` | 115 000 000 пользователей в день | Microsoft Teams, октябрь 2020; консервативная оценка дневной аудитории [^2] |
| `MF_DMP` | 300 000 000 участий во встречах в день | Zoom, апрель 2020; один пользователь может войти в несколько встреч [^3] |
| `MF_MEET_SIZE` | 10 участников | Средняя встреча Zoom, 15.11.2020–15.11.2021 [^4] |
| `MF_MEET_LEN_MIN` | 54 минуты | Там же [^4] |
| `MF_VIDEO_UP_MBPS` / `MF_VIDEO_DOWN_MBPS` | 2.6 / 1.8 Мбит/с на участника | 720p group video, требования Zoom [^5] |
| `MF_VIDEO_HQ_MBPS` | 1.0 / 0.6 Мбит/с | Group «high-quality video» ниже 720p [^5]; профиль при отказе ДЦ (п. 9.2) |
| `MF_AUDIO_MBPS` | 0.08 Мбит/с | Верхняя граница 60–80 kbps для VoIP [^5] |
| `MF_SCREEN_MBPS_MAX` | 0.15 Мбит/с | Верхняя граница 50–150 kbps для демонстрации экрана [^5] |
| `MF_CHAT_MSG_LIMIT` | 4 000 символов | Лимит сообщения Zoom Team Chat [^6] |
| `MF_CHAT_PER_JOIN` | 5 сообщений на участие | **Допущение**: публичной частоты нет [^6] |
| `MF_CHAT_MSG_SIZE` | 1 KB в среднем, до ≈ 10 KB | Допущение |
| `MF_LIST_PER_DAU` | 3 открытия списка встреч в сутки | Допущение |
| `MF_LOGIN_PER_DAU` | 1 логин в сутки | Допущение |
| `MF_CHAT_HISTORY_PER_JOIN` | 1 загрузка истории чата на участие | Допущение: при входе и после переподключения |
| `MF_REC_VIEWS_PER_REC` | не больше 1 открытия на запись | Допущение, верхняя оценка |
| `MF_REC_PART_MB` | 8 MB | Часть multipart upload: запись 0.761 GB — это ≈ 95 частей, S3 допускает до 10 000 [^46] |
| `MF_RECORD_QUOTA_GB` | 10 GB на пользователя | Квота Zoom Pro/Business [^8] |
| `MF_HEARTBEAT_SEC` | 25 секунд | `pingInterval` в Socket.IO по умолчанию [^9] |
| `MF_K_PEAK` | **1.5** | Пиковый час / среднее за сутки; одинаково для RPS, полосы и соединений. Сервис глобальный: часовые пояса сглаживают суточную кривую |

Все числа разделов 2–6, 9 и 11 считает скрипт [`resource/calc/meetflow_calc.py`](../resource/calc/meetflow_calc.py): чтобы поменять допущение, достаточно изменить константу и перезапустить. ВВП для долей ДЦ (приложение 3) — в [`imf_weo_2026apr_gdp_2025.json`](../resource/calc/imf_weo_2026apr_gdp_2025.json).

## Производные величины

| Название | Расчет | Значение |
| -------- | ------ | -------: |
| `MF_MEETINGS_DAY` | `MF_DMP / MF_MEET_SIZE` = `300 000 000 / 10` | **30 000 000 встреч/сутки** |
| `MF_JOINS_PER_DAU_DAY` | `MF_DMP / MF_DAU` = `300 000 000 / 115 000 000` | **2.61 подключения/DAU/день** |
| `MF_CREATED_MEETINGS_PER_DAU_DAY` | `MF_MEETINGS_DAY / MF_DAU` = `30 000 000 / 115 000 000` | **0.26 созданных встреч/DAU/день** |
| `MF_PARTICIPANT_MIN_DAY` | `MF_DMP * MF_MEET_LEN_MIN` = `300 000 000 * 54` | **16 200 000 000 participant-minutes/сутки** |
| `MF_AVG_ONLINE_PARTICIPANTS` | `MF_PARTICIPANT_MIN_DAY / 1440` | **11 250 000 участников online в среднем** |
| `MF_PEAK_ONLINE_PARTICIPANTS` | `MF_AVG_ONLINE_PARTICIPANTS * MF_K_PEAK` = `11 250 000 * 1.5` | **16 875 000 участников online в пик** |
| `MF_PEAK_WSS_CONNECTIONS` | `= MF_PEAK_ONLINE_PARTICIPANTS`, одно WSS-соединение на участника | **16 875 000 одновременных соединений** |
| `MF_PEAK_ACTIVE_MEETINGS` | `MF_PEAK_ONLINE_PARTICIPANTS / MF_MEET_SIZE` | **1 687 500 встреч одновременно** |
| `MF_HEARTBEAT_EVENTS_DAY` | `MF_PARTICIPANT_MIN_DAY * 60 / MF_HEARTBEAT_SEC` | **38 880 000 000 heartbeat-событий/сутки** |
| `MF_CHAT_MESSAGES_DAY` | `MF_DMP * MF_CHAT_PER_JOIN` = `300 000 000 * 5` | **1 500 000 000 сообщений/сутки** |
| `MF_MEETING_LIST_VIEWS_DAY` | `MF_DAU * MF_LIST_PER_DAU` = `115 000 000 * 3` | **345 000 000 открытий списка/сутки** |
| `MF_LOGINS_DAY` | `MF_DAU * MF_LOGIN_PER_DAU` | **115 000 000 логинов/сутки** |

Проверка по аналогу: на 31.10.2020 Zoom раскрывал годовой run rate более 3.5 трлн минут встреч [^3] — это ≈ 9.6 млрд минут в сутки. У нас 16.2 млрд, потому что каждый участник сидит во встрече все 54 минуты. Ошибка в безопасную сторону: онлайн, трафик и число SFU завышены, а не занижены.

## Продуктовые метрики: как посчитано

Средний размер хранилища пользователя — на одного MAU, данные за 30 дней:

| Тип данных | Штук на пользователя | Объем на пользователя | Расчет |
| ---------- | -------------------: | --------------------: | ------ |
| Профиль | 1 | 256 B | — |
| Созданные встречи (метаданные) | 2.81 | 720 B | 900 млн встреч за 30 дней / 320 млн MAU |
| Ссылки-приглашения | 2.81 | 360 B | одна ссылка на встречу, 128 B |
| Участия во встречах | 28.1 | 3.6 KB | 9 млрд участий за 30 дней / 320 млн MAU, 128 B |
| Строки списка встреч | 28.1 | 3.6 KB | одна строка на участие, 128 B |
| Сообщения чата | 140.6 | 140.6 KB | 45 млрд сообщений / 320 млн MAU, 1 KB |
| **Итого без записей** | — | **≈ 149 KB** | |
| Записи встреч, worst-case | 2.81 | **2.14 GB** | 2.81 записи × 0.761 GB; у аналога квота — 10 GB [^8] |

Среднее количество действий пользователя в сутки — на одного DAU:

| Действие | На DAU в сутки | Расчет |
| -------- | -------------: | ------ |
| Логин | 1.00 | `MF_LOGIN_PER_DAU` |
| Создание встречи | 0.26 | 30 млн / 115 млн |
| Вход во встречу (`join`) | 2.61 | 300 млн / 115 млн |
| Выход из встречи (`leave`) | 2.61 | одно на каждый вход |
| Сообщение в чат встречи | 13.04 | 1.5 млрд / 115 млн |
| Загрузка истории чата | 2.61 | одна на каждый вход |
| Открытие списка встреч | 3.00 | `MF_LIST_PER_DAU` |
| Метаданные записи | ≤ 0.26 | не больше одной записи на встречу |
| Открытие записи | ≤ 0.26 | `MF_REC_VIEWS_PER_REC` |
| Heartbeat, автоматически | 338.09 | 38.88 млрд / 115 млн |

## Хранение: формулы

| Блок данных | Расчет | Штук | Общий объем |
| ----------- | ------ | ---: | ----------: |
| Профили пользователей | `MF_MAU * 256 B` | 320 млн | **81.92 GB** |
| Метаданные встреч, 30 дней | `MF_MEETINGS_DAY * 30 * 256 B` | 900 млн | **230.4 GB** |
| Ссылки-приглашения, 30 дней | `MF_MEETINGS_DAY * 30 * 128 B` | 900 млн | **115.2 GB** |
| Участники встреч, 30 дней | `MF_DMP * 30 * 128 B` | 9 млрд | **1.152 TB** |
| Списки встреч пользователей, 30 дней | `MF_DMP * 30 * 128 B` | 9 млрд | **1.152 TB** |
| Активные сессии | `MF_DAU * 128 B` | 115 млн | **14.72 GB** |
| Чат встречи, 30 дней | `MF_CHAT_MESSAGES_DAY * 30 * MF_CHAT_MSG_SIZE` | 45 млрд | **45 TB** |
| **Техническое хранение без записей** | сумма строк выше, без репликации | — | **47.75 TB** |
| Размер одной записи | `MF_RECORDING_SIZE_GB = (MF_VIDEO_DOWN_MBPS + MF_AUDIO_MBPS) * MF_MEET_LEN_MIN * 60 / 8 / 1000` | — | **0.761 GB** |
| Записи в сутки, worst-case | `MF_MEETINGS_DAY * MF_RECORDING_SIZE_GB` | 30 млн | **22.842 PB/сутки** |
| Записи за 30 дней, worst-case | `22.842 PB * 30` | 900 млн | **685.26 PB** |
| **Суммарное хранение, 30 дней** | записи + техническое хранение | — | **≈ 685.31 PB** |

Квота аналога (10 GB на пользователя, 3.2 EB на всех) — это лимит, а не занятое место. Object storage считаем по worst-case: каждая встреча записывается и хранится 30 дней.

## Трафик: формулы

```text
суточный объем, GB  = MF_PARTICIPANT_MIN_DAY * 60 * битрейт_Мбит/с / 8 / 1000
avg_bandwidth_Gbps  = MF_AVG_ONLINE_PARTICIPANTS * битрейт_Мбит/с / 1000
peak_bandwidth_Gbps = avg_bandwidth_Gbps * MF_K_PEAK
rec_stream_Gbps     = (MF_AVG_ONLINE_PARTICIPANTS / MF_MEET_SIZE) * (1.8 + 0.08) / 1000 * K
запись, GB/сутки    = MF_PARTICIPANT_MIN_DAY / MF_MEET_SIZE * 60 * 1.88 / 8 / 1000   # битрейт на встречу
```

Поток в запись не уходит в интернет: SFU отправляет его recording workers внутри ДЦ как еще одному подписчику встречи. Он нагружает SFU и воркеры, поэтому учтен в разделе 11.

## RPS: события в сутки и формулы

| Метод / событие | Событий в сутки | Средний RPS | Пиковый RPS |
| --------------- | --------------: | ----------: | ----------: |
| `POST /auth/login` | `MF_LOGINS_DAY` = 115 000 000 | **1 331** | **1 997** |
| `POST /meetings` | `MF_MEETINGS_DAY` = 30 000 000 | **347** | **521** |
| `POST /meetings/{id}/join` | `MF_DMP` = 300 000 000 | **3 472** | **5 208** |
| `POST /meetings/{id}/leave` | `MF_DMP` = 300 000 000 | **3 472** | **5 208** |
| `WS /presence/heartbeat` | `MF_HEARTBEAT_EVENTS_DAY` = 38 880 000 000 | **450 000** | **675 000** |
| `POST /meeting-chat/messages` | `MF_CHAT_MESSAGES_DAY` = 1 500 000 000 | **17 361** | **26 042** |
| `GET /meeting-chat/messages?after_seq=N` | `MF_DMP * MF_CHAT_HISTORY_PER_JOIN` = 300 000 000 | **3 472** | **5 208** |
| `GET /users/{id}/meetings?limit=100` | `MF_MEETING_LIST_VIEWS_DAY` = 345 000 000 | **3 993** | **5 990** |
| `POST /recordings/metadata` | до `MF_MEETINGS_DAY` = 30 000 000 | **до 347** | **до 521** |
| `GET /recordings/{id}` — ссылка на скачивание | до `MF_MEETINGS_DAY * MF_REC_VIEWS_PER_REC` = 30 000 000 | **до 347** | **до 521** |
| WS push: чат и события join/leave остальным участникам | `(chat + join + leave) * (MF_MEET_SIZE − 1)` | **218 750** | **328 125** |

```text
avg_RPS  = events_per_day / 86400
peak_RPS = avg_RPS * MF_K_PEAK
```

Пики считаются от неокругленных значений, поэтому суммы округленных чисел в таблицах могут расходиться с итогом на единицу.

`GET /recordings/{id}` отдает только presigned URL: файл клиент скачивает напрямую из object storage `home_dc` (`rec.<dc>`, п. 3.5), мимо L7 и SFU. Частота просмотров неизвестна, поэтому трафик скачивания в таблицу не входит; его тариф — в приложении 11.

## Источники

[^1]: [Microsoft Investor Relations — Earnings Conference Call FY24 Q1 (транскрипт: «more than 320 million monthly active users» у Teams)](https://www.microsoft.com/en-us/investor/events/fy-2024/earnings-fy-2024-q1)

[^2]: [Microsoft 365 Blog — Microsoft Teams reaches 115 million DAU](https://www.microsoft.com/en-us/microsoft-365/blog/2020/10/28/microsoft-teams-reaches-115-million-dau-plus-a-new-daily-collaboration-minutes-metric-for-microsoft-365/)

[^3]: [Zoom Video Communications — Prospectus Supplement (Form 424B5), SEC, 13.01.2021: «In April 2020, our platform surpassed more than 300 million daily meeting participants»; run rate более 3.5 трлн минут встреч в год на 31.10.2020](https://www.sec.gov/Archives/edgar/data/1585521/000119312521008153/d919929d424b5.htm)

[^4]: [Zoom Blog — Here’s How You Zoomed Over the Past Year](https://www.zoom.com/en/blog/how-you-zoomed-over-the-past-year-2021/)

[^5]: [Zoom Support — Zoom system requirements: Zoom Web App](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0058323)

[^6]: [Zoom Support — Zoom Chat specifications and limitations](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0079326)

[^8]: [Zoom Support — Cloud recording storage capacity](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0067670)

[^9]: [Socket.IO Documentation — Server options](https://socket.io/docs/v4/server-options/)

[^46]: [Amazon S3 Documentation — Multipart upload overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)
