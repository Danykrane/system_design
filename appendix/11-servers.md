# Приложение 11. Серверы: нормативы, расчет по сервисам, стоимость

К основной части: [раздел 11](../README.md#11-список-серверов). Номера «п. X.Y» — пункты основной части.

Серверы считаются **по каждому ДЦ**: данные встречи живут в ее `home_dc` (п. 3.4), поэтому в каждом ДЦ свой набор кластеров. Общее правило — `ceil(нагрузка_ДЦ / емкость_узла) + 1` (`N+1` в каждом ДЦ) с минимальным размером кластера, которого требует технология.

## Нормативы и бенчмарки

| Компонент | Норматив / бенчмарк | Как используется | Источник |
| --------- | ------------------- | ---------------- | -------- |
| 8 ДЦ | ДЦ из п. 3.2; у Selectel 6 регионов в 4 странах, наших 8 городов среди них нет | Цены Selectel — ориентир для всех ДЦ: на 11.10.2026 с НДС 22%, курс ЦБ РФ на 10.10.2026 — 84.90 ₽ за $1 | [^64][^65][^99] |
| `Kubernetes-кластер/3 зоны доступности` | Managed Kubernetes HA: 3 master-ноды | один HA-кластер на ДЦ | [^69] |
| `L4: IPVS + keepalived` | EL11-SSD-10GE: 10GE, 32 GB; 136 B на соединение в таблице IPVS | 2 директора на ДЦ, active/standby (п. 4.4) | [^66][^91][^93] |
| `Ingress L7 (NGINX)` | 341 232 HTTPS RPS; 6 676 новых TLS/с; 8.8 Gbps; 54 KB на WSS-соединение | расчет узлов L7, приложение 4 | [^19][^20][^77][^78] |
| Ядро SFU | Jitsi Videobridge: 550.4 Мбит/с при 20.3% CPU 4-ядерного сервера, CPU растет почти линейно с битрейтом. Экстраполяция до 100% — наше допущение: `550.4 / 0.203 / 4 ≈ 0.678 Гбит/с на ядро` | целевая загрузка CPU 70% → 0.4745 Гбит/с на ядро | [^74] |
| `Пул SFU (медиа)` | EL11-SSD-10GE, 6 ядер: `min(10 Gbps NIC; 6 × 0.4745) = 2.847 Gbps` на узел | ограничитель — CPU, а не сетевая карта; SFU масштабируется по ядрам: один mediasoup worker = одно ядро [^76] | [^66][^74][^75][^76] |
| `Воркеры записи` | те же 2.847 Gbps на узел: расшифровка SRTP и упаковка потока без перекодирования — допущение по аналогии с SFU | расчет по потоку в запись (п. 2.4) | [^66][^74] |
| WebSocket-под | 4 CPU / 8 GB, 6 GB под соединения, ≤ 20 KB на соединение по аналогии с замером NGINX → **300 000 соединений на под** | heartbeat на под ≈ 12 000/с | [^77] |
| Поды Auth / Control Plane / Chat | 1 000 / 1 500 / 5 000 запросов/с на под 4 CPU / 8 GB | проектный норматив для C++-сервиса с точечными запросами без JOIN | — |
| Redis | один шард ≈ 120 000 ops/s: redis-benchmark без пайплайнинга дает 72–180 тыс. запросов/с | `max(3, ceil(ops_ДЦ / 120 000))` master | [^31][^79] |
| ScyllaDB | CL34-NVMe: 2×1 TB NVMe. Заполняем не больше 50%: при compaction со стратегией STCS в худшем случае нужна свободной половина диска [^95] → ≤ 1 TB данных на узел | `max(3, ceil(объем_с_RF / 1 TB))`; отдельный `+1` не нужен: при RF=3 данные каждого узла есть еще на двух | [^33][^66][^95] |

**Сверка SFU с LiveKit.** LiveKit тестировал свой SFU на 16-ядерном инстансе Google Cloud `c2-standard-16` [^75]. С пакетами размером с видео (≈ 950 байт) — 4.25 Гбит/с при 92% CPU, то есть ≈ 0.29 Гбит/с на ядро. С мелкими пакетами (≈ 120 байт, встреча 150 × 150) — лишь ≈ 0.08 Гбит/с на ядро: SFU нагружают пакеты в секунду, а не биты. Во встрече на 10 человек основной трафик — пакеты видео 720p, поэтому за основу взят замер Jitsi. Оценка оптимистичная: если пакеты окажутся мельче, SFU понадобится больше.

## Цены Selectel

| Позиция | Цена и параметры | Где используется | Источник |
| ------- | ---------------- | ---------------- | -------- |
| `Объектное хранилище S3 / ≥3 копий` | ледяное хранение — 0.89 ₽/GB в месяц, исходящий трафик — 1.96 ₽/GB | записи встреч: 685.26 PB / 30 дней | [^70] |
| `Cloud Server custom flavor` | 1 vCPU = 735.19 ₽/мес; 1 GB RAM = 267.34 ₽/мес; 1 GB SSD = 10.48 ₽/мес | узлы L7 | [^67][^68] |
| `EL11-SSD-10GE` | 6 ядер, 32 GB RAM, 2×480 GB SSD, 10GE, 14 000 ₽/мес | SFU, recording workers, L4 | [^66] |
| `CL34-NVMe` | 14 ядер, 64 GB RAM, 2×1 TB NVMe, 13 600 ₽/мес | app pool, Redis, ScyllaDB, наблюдаемость | [^66] |
| `BL18-NVMe` | 16 ядер, 128 GB RAM, 2×1920 GB + 1000 GB NVMe, 34 900 ₽/мес | PostgreSQL `auth_pg` и Citus | [^66] |
| Трафик выделенного сервера | при порте больше 1 Гбит/с — 300 TB в месяц без ограничения полосы (или 1 Гбит/с без учета объема); сверх лимита — 336 ₽/мес за шаг 3 TB; при среднем потоке больше 100 Мбит/с — индивидуальные условия | оценка внешнего трафика SFU, раздел «Внешний трафик» ниже | [^71][^66] |

## Расчет ресурсов по сервисам

### Балансировка, медиа и сервисы

| Сервис | Пиковая нагрузка, весь мир | Правило на ДЦ | Итоговые ресурсы | Источник |
| ------ | -------------------------- | ------------- | ---------------- | -------- |
| `GeoDNS / GTM` | 8 ДЦ | managed-сервис | 0 серверов | [^16][^17] |
| `Anycast DNS` | NS-серверы GTM | managed у DNS-провайдера | 0 серверов | [^83] |
| `L4: IPVS + keepalived` | 16 875 000 соединений (2.29 GB таблиц IPVS), входящий трафик ≤ 8.43 Gbps | `max(1, ceil(Gbps_ДЦ / 10)) + 1`, п. 4.4 | 16 узлов EL11-SSD-10GE | [^91][^92][^93] |
| `Ingress L7 (NGINX)` | 1 054 340 RPS, 56 424 новых TLS/с, 8.43 Gbps, 16 875 000 WSS | п. 4.4 и приложение 4, `N+1` | 28 узлов × `24 vCPU / 64 GB` | [^19][^20][^77][^78] |
| `Пул SFU (медиа)` | 78 131.25 Gbps media + 3 172.5 Gbps поток в запись = **81 303.75 Gbps** | `ceil(Gbps_ДЦ / 2.847) + 1` | 28 570 серверов × `6 CPU / 32 GB / 10GE` | [^66][^74] |
| `Воркеры записи` | 3 172.5 Gbps | `ceil(Gbps_ДЦ / 2.847) + 1` | 1 127 серверов × `6 CPU / 32 GB / 10GE` | [^66][^74] |
| `Аутентификация Users API` | 7 726 RPS: login + чтение `users` при create/join | `ceil(RPS_ДЦ / 1 000) + 1` | 20 подов × `4 CPU / 8 GB` | расчет по п. 5.2 |
| `Управление встречами` | 17 969 RPS: create + join + leave + list + метаданные записи + открытие записи | `ceil(RPS_ДЦ / 1 500) + 1` | 23 пода × `4 CPU / 8 GB` | расчет по п. 2.5 |
| `WebSocket / присутствие` | 16 875 000 соединений, 675 000 heartbeat/с | `ceil(соединений_ДЦ / 300 000) + 1` | 69 подов × `4 CPU / 8 GB` | расчет по п. 2.1 |
| `Чат встречи` | 31 250 запросов/с: сообщения 26 042 + история 5 208 | `ceil(RPS_ДЦ / 5 000) + 1` | 19 подов × `4 CPU / 8 GB` | расчет по п. 2.5 |
| `PgBouncer` | соединения к `auth_pg`, `meeting_pg`, `recording_pg` | 3 пода на ДЦ | 24 пода × `2 CPU / 2 GB` | [^32] |
| `Kubernetes app pool` | 572 CPU подов | `ceil(CPU_ДЦ / 12) + 1` (2 из 14 ядер — ОС и kubelet) | 59 узлов CL34-NVMe | [^66] |

### Хранилища и наблюдаемость

| Сервис | Пиковая нагрузка, весь мир | Правило на ДЦ | Итоговые ресурсы | Источник |
| ------ | -------------------------- | ------------- | ---------------- | -------- |
| `Redis` (session + runtime) | runtime: 738 021 ops/s; sessions: 14 236 ops/s. Сессии — 14.72 GB, в самом большом ДЦ ≈ 5.3 GB, с репликой ≈ 10.5 GB | `max(3, ceil(ops_ДЦ / 120 000))` узлов; оба кластера на одних серверах: на каждом master одного шарда и replica другого | 24 узла CL34-NVMe | [^31][^79] |
| `PostgreSQL auth_pg` | 81.92 GB, 7 726 чтений/с, ≤ 1 997 записей/с | primary + sync standby в `DC-US-EAST`, по одной реплике в остальных ДЦ | 9 узлов BL18-NVMe | [^27][^86] |
| `PostgreSQL + Citus` (`meeting_pg` + `recording_pg`) | 576 GB метаданных, 16 667 чтений/с; в самом большом ДЦ — 206 GB и ≈ 5 950 чтений/с | в ДЦ координатор с локальными шардами + standby, плюс реплика парного ДЦ | 24 узла BL18-NVMe | [^29][^90] |
| `ScyllaDB meeting_scylla/RF=3` | 31.10 TB с репликацией: копия `user_meetings` в каждом ДЦ + participants своего ДЦ | `max(3, ceil(TB_ДЦ / 1))` | 34 узла CL34-NVMe | [^33][^80] |
| `ScyllaDB chat_scylla/RF=3` | 135 TB с репликацией | `max(3, ceil(TB_ДЦ / 1))` | 138 узлов CL34-NVMe | [^33] |
| `Объектное хранилище S3 / ≥3 копий` | 685.26 PB / 30 дней | хранение в `home_dc` | Managed S3 | [^70] |
| `Наблюдаемость` | метрики, логи, трассы | 2 узла на ДЦ + 2 центральных в `DC-US-EAST` | 18 узлов CL34-NVMe | [^56][^57][^58][^59][^60] |

## Поды Kubernetes по ДЦ

| ДЦ | Auth | Control Plane | WebSocket | Chat | PgBouncer | CPU подов | Узлы app pool |
| -- | --: | --: | --: | --: | --: | --: | --: |
| `DC-US-EAST` | 4 | 5 | 18 | 3 | 3 | 126 | 12 |
| `DC-US-WEST` | 2 | 2 | 6 | 2 | 3 | 54 | 6 |
| `DC-BR-SAOPAULO` | 2 | 2 | 4 | 2 | 3 | 46 | 5 |
| `DC-UK-LONDON` | 2 | 2 | 4 | 2 | 3 | 46 | 5 |
| `DC-DE-FRANKFURT` | 4 | 6 | 22 | 4 | 3 | 150 | 14 |
| `DC-IN-MUMBAI` | 2 | 2 | 4 | 2 | 3 | 46 | 5 |
| `DC-SG-SINGAPORE` | 2 | 2 | 5 | 2 | 3 | 50 | 6 |
| `DC-JP-TOKYO` | 2 | 2 | 6 | 2 | 3 | 54 | 6 |
| **Итого** | **20** | **23** | **69** | **19** | **24** | **572** | **59** |

## Объем ScyllaDB по ДЦ

| ДЦ | meeting_scylla, с RF | Узлов | chat_scylla, с RF | Узлов |
| -- | --: | --: | --: | --: |
| `DC-US-EAST` | 4.45 TB | 5 | 38.93 TB | 39 |
| `DC-US-WEST` | 3.71 TB | 4 | 9.99 TB | 10 |
| `DC-BR-SAOPAULO` | 3.62 TB | 4 | 6.28 TB | 7 |
| `DC-UK-LONDON` | 3.60 TB | 4 | 5.48 TB | 6 |
| `DC-DE-FRANKFURT` | 4.69 TB | 5 | 48.18 TB | 49 |
| `DC-IN-MUMBAI` | 3.63 TB | 4 | 6.79 TB | 7 |
| `DC-SG-SINGAPORE` | 3.70 TB | 4 | 9.41 TB | 10 |
| `DC-JP-TOKYO` | 3.71 TB | 4 | 9.94 TB | 10 |
| **Итого** | **31.10 TB** | **34** | **135.00 TB** | **138** |

## Реплики Citus в парных ДЦ

`Citus` = координатор + standby своего ДЦ + реплики парных ДЦ: в `DC-US-EAST` хранятся реплики `DC-US-WEST` и `DC-BR-SAOPAULO`, в `DC-SG-SINGAPORE` — `DC-IN-MUMBAI` и `DC-JP-TOKYO`.

## Сводка по конфигурациям

| Пул / сервис | Конфигурация одного сервера | Кол-во | Итого CPU | Итого RAM | Сеть | Что размещается |
| ------------ | --------------------------- | -----: | --------: | --------: | ---- | --------------- |
| `Kubernetes-кластер/3 зоны доступности` | Managed Kubernetes HA | 8 | — | — | сеть провайдера | master-ноды Kubernetes, по одному кластеру на ДЦ |
| `L4: IPVS + keepalived` | `EL11-SSD-10GE`: 6 CPU, 32 GB RAM, 10GE | 16 | 96 | 512 GB | ≤ 3.01 Gbps входящего на ДЦ при 10GE | директоры IPVS, keepalived |
| `Ingress L7 (NGINX)` | `24 vCPU / 64 GB / 100 GB SSD` | 28 | 672 | 1 792 GB | `8.43 Gbps / 28 ≈ 0.30 Gbps` на узел | `Ingress L7 (NGINX)` |
| `Kubernetes app pool` | `CL34-NVMe`: 14 CPU, 64 GB RAM | 59 | 826 | 3 776 GB | 1 Gbps на узел достаточно для control plane | Auth, Control Plane, WebSocket, Chat, PgBouncer |
| `Пул SFU (медиа)` | `EL11-SSD-10GE`: 6 CPU, 32 GB RAM, 10GE | 28 570 | 171 420 | 914 240 GB | 2.847 Gbps на узел при NIC 10 Gbps; оптический порт по заявке [^71] | `Пул SFU (медиа)` |
| `Воркеры записи` | `EL11-SSD-10GE`: 6 CPU, 32 GB RAM, 10GE | 1 127 | 6 762 | 36 064 GB | 2.847 Gbps на узел | `Воркеры записи` |
| `Redis` (session + runtime) | `CL34-NVMe`: 14 CPU, 64 GB RAM | 24 | 336 | 1 536 GB | 1 Gbps на узел | `session_redis`, `runtime_redis` |
| `PostgreSQL auth_pg` | `BL18-NVMe`: 16 CPU, 128 GB RAM | 9 | 144 | 1 152 GB | 1 Gbps на узел | primary, standby, реплики |
| `PostgreSQL + Citus` | `BL18-NVMe`: 16 CPU, 128 GB RAM | 24 | 384 | 3 072 GB | 1 Gbps на узел | `meeting_pg`, `recording_pg` |
| `ScyllaDB meeting_scylla/RF=3` | `CL34-NVMe`: 14 CPU, 64 GB, 2×1 TB NVMe | 34 | 476 | 2 176 GB | 1 Gbps на узел | `meeting_participants`, `user_meetings` |
| `ScyllaDB chat_scylla/RF=3` | `CL34-NVMe`: 14 CPU, 64 GB, 2×1 TB NVMe | 138 | 1 932 | 8 832 GB | 1 Gbps на узел | `chat_messages` |
| `Объектное хранилище S3 / ≥3 копий` | Managed S3 | — | — | — | сеть object storage | записи встреч |
| `Наблюдаемость (HA)` | `CL34-NVMe`: 14 CPU, 64 GB RAM | 18 | 252 | 1 152 GB | 1 Gbps на узел | Prometheus, OpenTelemetry, Loki в ДЦ; Grafana, Jaeger центрально |

## Стоимость подробно

Цены Selectel на 11.10.2026 с НДС 22% (раздел «Цены Selectel» выше). В доллары пересчитано по курсу ЦБ РФ на 10.10.2026: 84.90 ₽ за $1 [^99].

| Пул / сервис | Кол-во | Ближайшая публичная конфигурация Selectel | Цена за 1 узел / мес. | Итого / мес. | Комментарий |
| ------------ | -----: | ----------------------------------------- | --------------------: | -----------: | ----------- |
| `Kubernetes-кластер/3 зоны доступности` | 8 | Managed Kubernetes HA, 3 master-ноды | 17 085.59 ₽ | 136 684.72 ₽ | по одному HA-кластеру на ДЦ [^69] |
| `L4: IPVS + keepalived` | 16 | `EL11-SSD-10GE` | 14 000 ₽ | 224 000 ₽ | active/standby в каждом ДЦ [^66] |
| `Ingress L7 (NGINX)` | 28 | Cloud Server custom flavor | 35 802.32 ₽ | 1 002 464.96 ₽ | `24*735.19 + 64*267.34 + 100*10.48` [^67] |
| `Kubernetes app pool` | 59 | `CL34-NVMe` | 13 600 ₽ | 802 400 ₽ | API, WS, chat, PgBouncer [^66] |
| `Пул SFU (медиа)` | 28 570 | `EL11-SSD-10GE` | 14 000 ₽ ≈ $164.90 | 399 980 000 ₽ | без внешнего трафика, он оценен ниже [^66] |
| `Воркеры записи` | 1 127 | `EL11-SSD-10GE` | 14 000 ₽ ≈ $164.90 | 15 778 000 ₽ | поток в запись идет внутри ДЦ [^66] |
| `Redis` (session + runtime) | 24 | `CL34-NVMe` | 13 600 ₽ | 326 400 ₽ | узкое место — ops/s [^31][^66] |
| `PostgreSQL auth_pg` | 9 | `BL18-NVMe` | 34 900 ₽ | 314 100 ₽ | профили и auth [^66] |
| `PostgreSQL + Citus` | 24 | `BL18-NVMe` | 34 900 ₽ | 837 600 ₽ | метаданные встреч и записей [^66] |
| `ScyllaDB meeting_scylla/RF=3` | 34 | `CL34-NVMe` | 13 600 ₽ | 462 400 ₽ | participants + user meetings [^33][^66] |
| `ScyllaDB chat_scylla/RF=3` | 138 | `CL34-NVMe` | 13 600 ₽ | 1 876 800 ₽ | chat append-only log [^66] |
| `Объектное хранилище S3 / ≥3 копий` | 685 260 000 GB | S3 ледяное хранение | 0.89 ₽/GB | 609 881 400 ₽ | только хранение, без запросов и исходящего трафика [^70] |
| `Наблюдаемость (HA)` | 18 | `CL34-NVMe` | 13 600 ₽ | 244 800 ₽ | 2 узла на ДЦ + 2 центральных [^66] |
| **Итого: серверы и хранение** | — | — | — | **1 031 867 049.68 ₽/мес** | **≈ $12 153 911.07/мес** |

| Структура расходов | Сумма / мес. | Доля |
| ------------------ | -----------: | ---: |
| Хранение записей, S3 | 609.88 млн ₽ | 59.1% |
| Медиа, SFU | 399.98 млн ₽ | 38.8% |
| Воркеры записи | 15.78 млн ₽ | 1.5% |
| Все остальное: балансировка, сервисы, БД, наблюдаемость | 6.23 млн ₽ | 0.6% |

## Внешний трафик

Цены выделенных серверов не покрывают наш трафик: при порте больше 1 Гбит/с Selectel дает 300 TB в месяц без ограничения полосы, а расширение стоит 336 ₽/мес за шаг 3 TB [^71][^66]. Через порты SFU проходит весь медиатрафик:

```text
медиа за месяц     = 562 545 000 GB/сутки * 30 = 16 876 350 TB ≈ 16.9 EB  (≈ 591 TB на узел SFU)
входит в тарифы    = 300 TB * 28 570 узлов     = 8 571 000 TB
сверх лимита       = 8 305 350 TB → 2 768 450 шагов по 3 TB * 336 ₽ ≈ 930.20 млн ₽/мес
```

Это верхняя оценка по публичному тарифу: на таком объеме трафик покупают по индивидуальному договору (транзит и пиринг), и он выходит дешевле. Поэтому в итог выше трафик не включен. С ним по публичному тарифу итог — **≈ 1 962.07 млн ₽/мес (≈ $23.11 млн)**, и трафик становится крупнейшей статьей. Исходящий трафик S3 при скачивании записей (1.96 ₽/GB [^70]) тоже не включен: частота просмотров неизвестна (п. 2.5).

Стоимость определяют те же блоки, что и нагрузку: хранение записей, медиа и внешний трафик медиа.

## Источники

[^16]: [Cloudflare Docs — Global traffic steering policies](https://developers.cloudflare.com/load-balancing/understand-basics/traffic-steering/steering-policies/)

[^17]: [Cloudflare Docs — Create a monitor (минимальный интервал: 60 с Pro, 15 с Business, 10 с Enterprise; consecutive_down через API)](https://developers.cloudflare.com/load-balancing/monitors/create-monitor/)

[^19]: [NGINX Community Blog — Testing the Performance of NGINX Ingress Controller for Kubernetes](https://blog.nginx.org/blog/testing-performance-nginx-ingress-controller-kubernetes)

[^20]: [NGINX Community Blog — Testing the Performance of NGINX and NGINX Plus Web Servers](https://blog.nginx.org/blog/testing-the-performance-of-nginx-and-nginx-plus-web-servers)

[^27]: [PostgreSQL Documentation — Replication](https://www.postgresql.org/docs/current/runtime-config-replication.html)

[^29]: [Citus Documentation — Choosing Distribution Column](https://docs.citusdata.com/en/stable/sharding/data_modeling.html)

[^31]: [Redis Documentation — Redis Cluster Specification](https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/)

[^32]: [PgBouncer Documentation — Features](https://www.pgbouncer.org/features.html)

[^33]: [ScyllaDB Documentation — Fault Tolerance](https://docs.scylladb.com/manual/stable/architecture/architecture-fault-tolerance.html)

[^56]: [Prometheus Documentation — Overview](https://prometheus.io/docs/introduction/overview/)

[^57]: [Grafana Documentation — Grafana OSS and Enterprise](https://grafana.com/docs/grafana/latest/)

[^58]: [OpenTelemetry Documentation](https://opentelemetry.io/docs/)

[^59]: [Grafana Loki OSS — Log aggregation system](https://grafana.com/oss/loki/)

[^60]: [Jaeger Documentation — Introduction](https://www.jaegertracing.io/docs/latest/)

[^64]: [Selectel Documentation — Локации: страны, регионы, зоны доступности, пулы и адреса дата-центров](https://docs.selectel.ru/infrastructure/locations/)

[^65]: [Selectel Documentation — Product availability by location](https://docs.selectel.ru/en/infrastructure/product-availability-by-location/)

[^66]: [Selectel — Тарифы и цены на услуги: выделенные серверы](https://selectel.ru/prices/)

[^67]: [Selectel — Тарифы и цены на услуги: облачные серверы и балансировщики](https://selectel.ru/prices/)

[^68]: [Selectel Documentation — Cloud Server Configurations](https://docs.selectel.ru/en/cloud-servers/create/configurations/)

[^69]: [Selectel — Тарифы и цены на услуги: Managed Kubernetes](https://selectel.ru/prices/)

[^70]: [Selectel — Тарифы и цены на услуги: S3](https://selectel.ru/prices/)

[^71]: [Selectel Documentation — Dedicated server traffic consumption model](https://docs.selectel.ru/en/dedicated/networks/traffic-plans/)

[^74]: [Jitsi — Jitsi Videobridge Performance Evaluation](https://jitsi.org/jitsi-videobridge-performance-evaluation)

[^75]: [LiveKit Docs — Benchmarks](https://docs.livekit.io/transport/self-hosting/benchmark/)

[^76]: [mediasoup Documentation — Scalability](https://mediasoup.org/documentation/v3/scalability/)

[^77]: [NGINX (F5) Blog — NGINX WebSocket Performance](https://www.f5.com/company/blog/nginx/nginx-websockets-performance)

[^78]: [OpenSSL Documentation — SSL_CTX_set_mode, SSL_MODE_RELEASE_BUFFERS](https://docs.openssl.org/3.5/man3/SSL_CTX_set_mode/)

[^79]: [Redis Docs — Redis benchmark](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/benchmarks/)

[^80]: [ScyllaDB Documentation — Create a ScyllaDB Cluster: Multi Data Centers](https://docs.scylladb.com/manual/stable/operating-scylla/procedures/cluster-management/create-cluster-multidc.html)

[^83]: [RFC 4786 — Operation of Anycast Services](https://datatracker.ietf.org/doc/html/rfc4786)

[^86]: [Patroni Documentation](https://patroni.readthedocs.io/en/latest/)

[^90]: [Citus Documentation — Single-Node Citus](https://docs.citusdata.com/en/stable/installation/single_node.html)

[^91]: [Linux kernel — net/netfilter/ipvs/Kconfig: запись в таблице соединений IPVS занимает 128 B, элемент хеш-таблицы — 8 B](https://github.com/torvalds/linux/blob/master/net/netfilter/ipvs/Kconfig)

[^92]: [Linux Virtual Server — Virtual Server via Direct Routing](https://www.linuxvirtualserver.org/VS-DRouting.html)

[^93]: [Keepalived Documentation — Introduction: IPVS, health checks, VRRP](https://keepalived.readthedocs.io/en/latest/introduction.html)

[^95]: [ScyllaDB Documentation — Compaction Strategies: STCS в худшем случае требует свободной половины диска](https://docs.scylladb.com/manual/stable/architecture/compaction/compaction-strategies.html)

[^99]: [Банк России — Официальные курсы валют на 10.10.2026: 84.9048 ₽ за $1](https://www.cbr.ru/currency_base/daily/?UniDbQuery.Posted=True&UniDbQuery.To=10.10.2026)
