# Приложение 7. Алгоритмы: альтернативы, шаги и структуры данных

К основной части: [раздел 7](../README.md#7-алгоритмы). Номера «п. X.Y» — пункты основной части.

## Adaptive Bitrate

**Задача** — подобрать качество видео под текущую сеть участника. **Вход:** `packet_loss`, `RTT`, `jitter`, `available_bitrate`, `frames_dropped`, `audio_quality`. **Результат:** `target_profile = 720p / 360p / 180p / audio_only`. **Ограничение:** звук важнее видео; понижение быстрое, повышение плавное.

Метрики сети SFU получает из RTCP внутри медиасессии: отчеты о приеме с потерями и джиттером [^44] и feedback о времени доставки пакетов для congestion control [^41]; клиент видит те же метрики через WebRTC stats API [^40]. Отдельных запросов к API ради статистики нет, поэтому в расчет нагрузки она не входит. Верхний профиль — 720p: на нем построен расчет трафика [^5]. 1080p в MVP нет: он требует 3.8/3.0 Мбит/с [^5] и увеличил бы трафик и число SFU.

| Альтернатива | Минус | Решение |
| ------------ | ----- | ------- |
| Всегда 720p | При плохой сети звонок рвется | Не подходит |
| Только клиент решает качество | SFU хуже управляет исходящим трафиком | Не выбираем |
| Server-guided ABR | SFU видит подписчиков и управляет слоями | **Выбрано** |

### Шаги

1. SFU получает RTCP-отчеты клиента — обычно несколько раз в секунду.
2. SFU оценивает сеть: потери, RTT, jitter, доступную полосу.
3. Сеть ухудшилась — профиль снижается сразу.
4. Сеть стабильна — профиль повышается на одну ступень.
5. Страдает звук — первым снижается видео.
6. Новый профиль применяется к подписке участника.

Состояние живет в памяти SFU: `participant_network_stats` (`meeting_id`, `user_id`, `loss`, `rtt`, `jitter`, `bitrate`) и `participant_media_profile` (`meeting_id`, `user_id`, `target_profile`, `updated_at`). Постоянные таблицы и Redis не меняются, метрики качества уходят в Prometheus. Эффект — меньше video download у участников с плохой сетью.

## Выбор SFU-слоя видео

**Задача** — не транскодировать видео, а выбирать готовый слой. **Вход:** `target_profile`, `viewport`, `active_speaker`, доступные encodings. **Результат:** `selected_layer` для каждого подписчика. **Ограничение:** SFU не должен превращаться в MCU с высоким CPU.

SFU маршрутизирует RTP-потоки [^44] между участниками, а не смешивает их в один поток [^14]. Для нескольких качеств используется simulcast / SVC: отправитель публикует несколько encodings, SFU выбирает нужный слой [^42].

| Альтернатива | Минус | Решение |
| ------------ | ----- | ------- |
| Single stream | Всем отдается одно качество | Плохо для слабой сети |
| MCU transcoding | Высокая CPU-нагрузка | Не подходит для highload |
| SFU + simulcast/SVC | Больше upload от отправителя, зато сервер не перекодирует видео | **Выбрано** |

### Шаги

1. Клиент публикует несколько слоев видео.
2. SFU хранит список доступных слоев каждого отправителя.
3. Для каждого подписчика считается `target_profile`.
4. Видео активного говорящего (его определяет active speaker detection [^43]) и крупной плитки отдается слоем выше.
5. Миниатюры отдаются слоем ниже.
6. При деградации сети SFU переключает подписчика на слой ниже.

Состояние живет в памяти SFU: `producer_layers` (`producer_id`, `rid`, `width`, `height`, `max_bitrate`), `consumer_subscription` (`consumer_id`, `producer_id`, `selected_layer`) и `participant_media_profile` (`user_id`, `target_profile`, `reason`). Новых постоянных таблиц нет. Эффект — меньше исходящего трафика SFU и никакого перекодирования на сервере.

## Источники

[^5]: [Zoom Support — Zoom system requirements: Zoom Web App](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0058323)

[^14]: [mediasoup Documentation — SFU overview](https://mediasoup.org/documentation/overview/)

[^40]: [W3C — Identifiers for WebRTC's Statistics API](https://www.w3.org/TR/webrtc-stats/)

[^41]: [RFC 8888 — RTP Control Protocol Feedback for Congestion Control](https://www.rfc-editor.org/rfc/rfc8888.html)

[^42]: [mediasoup Documentation — RTP Parameters and Capabilities](https://mediasoup.org/documentation/v3/mediasoup/rtp-parameters-and-capabilities/)

[^43]: [mediasoup Documentation — ActiveSpeakerObserver API](https://mediasoup.org/documentation/v3/mediasoup/api/#ActiveSpeakerObserver)

[^44]: [RFC 3550 — RTP: A Transport Protocol for Real-Time Applications](https://datatracker.ietf.org/doc/html/rfc3550)
