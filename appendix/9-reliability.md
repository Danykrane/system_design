# Приложение 9. Надежность: отказ дата-центра и расчет емкости

К основной части: [раздел 9](../README.md#9-обеспечение-надежности). Номера «п. X.Y» — пункты основной части.

## Резервирование: подробная таблица

### Сеть и сервисы

| Компонент | Что резервируем | Способ резервирования | Формула | При отказе |
| --------- | --------------- | --------------------- | ------- | ---------- |
| `GeoDNS / GTM` | Выбор ДЦ и переключение между ДЦ | Managed-сервис: health checks, geo/latency routing, веса пулов [^15][^16][^17] | 8 ДЦ, резервы по п. 3.7 | ДЦ убирается из DNS-ответов, новые подключения идут в здоровые ДЦ |
| `Anycast DNS` | NS-серверы GTM | Один Anycast IP из многих PoP провайдера [^83] | `N_PoP >= 2` | DNS-запросы уходят в ближайший живой PoP |
| `L4: IPVS + keepalived` | TCP-вход HTTPS/WSS в ДЦ | Пара директоров active/standby: VIP переезжает по VRRP, keepalived проверяет узлы NGINX [^91][^92][^93] | `N+1`: 2 на ДЦ | VIP за секунды переходит на резервный директор; оборванные соединения клиенты открывают заново |
| `NGINX L7 pool` | HTTPS/WSS, TLS termination | Active-active, health checks, запас по памяти под соединения [^19][^20][^77] | `N+1`, для strict HA — `N*2` | Клиенты переподключаются на живые L7-узлы |
| `Kubernetes` | Поды и узлы | Replicas, reschedule, self-healing [^54][^63] | `replicas >= 2`, `N+1` узлов | Под пересоздается, нагрузка переезжает на живой узел |
| Auth, Control Plane, Chat, WebSocket / Presence | Логин, встречи, чат, heartbeat | Stateless-поды: состояние — в БД и Redis, буфер чата собирается заново из ScyllaDB [^31][^54] | `N+1` в каждом ДЦ | Запрос уходит на живой под, WS-клиент переподключается |
| `SFU media pool` | Аудио, видео, screen sharing | Sticky meeting + health checks, SFU без смешивания потоков [^14][^42] | `N+1` в каждом ДЦ | Новые встречи не назначаются на плохой SFU; при отказе SFU клиент получает новый SFU и заново устанавливает с ним медиасоединение (ICE + DTLS) [^84] |
| `Recording workers` | Сборка и финализация записи | Пул воркеров, retry, multipart upload [^46] | `N+1` в каждом ДЦ | Незавершенную запись дописывает другой воркер: список загруженных частей он читает из S3 [^46] |

### Хранилища

| Компонент | Что резервируем | Способ резервирования | Формула | При отказе |
| --------- | --------------- | --------------------- | ------- | ---------- |
| `PostgreSQL auth_pg` | `users` | Primary в `DC-US-EAST` + синхронная standby в другой AZ + 7 реплик в остальных ДЦ, WAL/PITR, Patroni внутри ДЦ [^27][^28][^86][^89] | `1 primary + 1 sync standby + 7 async` | Standby становится primary без потери данных; при отказе всего `DC-US-EAST` дежурный повышает реплику `DC-US-WEST` [^97] |
| `PostgreSQL + Citus` (`meeting_pg`, `recording_pg`) | Встречи, ссылки, метаданные записей | В ДЦ координатор с шардами + синхронная standby; реплика в парном ДЦ; WAL/PITR [^27][^29][^90] | `2 в ДЦ + 1 в парном ДЦ` | Standby в соседней AZ; при отказе ДЦ дежурный повышает реплику в парном ДЦ [^97] |
| `PgBouncer` | Пул соединений PostgreSQL | Несколько инстансов перед БД [^32] | 3 на ДЦ | Приложение переключается на живой pooler |
| `Redis session_redis` | `user_sessions` | Redis Cluster: 3 master + 3 replica. Оба кластера ДЦ живут на 3 общих серверах: на каждом master одного шарда и replica другого (п. 11.1) [^31] | `3 master + 3 replica` на ДЦ | Replica становится master; потерянные сессии — повторный логин |
| `Redis runtime_redis` | `meetings_runtime`, `chat_seq`, `chat_dedup` | Redis Cluster + TTL для hot state [^22][^31] | `3 master + 3 replica` на ДЦ | Состояние встреч восстанавливают heartbeat-ы клиентов |
| `ScyllaDB meeting_scylla` | `meeting_participants`, `user_meetings` | Один кластер на все ДЦ: у participants keyspace ДЦ с RF=3, у `user_meetings` RF=3 в каждом ДЦ, `LOCAL_QUORUM` [^33][^80][^81] | `RF=3` | Отказ узла не останавливает чтение и запись, пока жив кворум ДЦ |
| `ScyllaDB chat_scylla` | `chat_messages` | Кластер в каждом ДЦ, append-only log, снапшоты в S3 парного ДЦ [^33] | `RF=3` | Чтение и запись работают при отказе узла |
| `S3-compatible Object Storage` | Записи встреч и части загрузки | Multipart upload, strong consistency, ≥ 3 копии в 3 AZ `home_dc` [^23][^24][^46] | `>=3 copies` | Файл доступен, незавершенные части можно дозагрузить |
| Наблюдаемость | Метрики, логи, трассы | Prometheus, OpenTelemetry, Loki в каждом ДЦ; Grafana, Jaeger центрально [^56][^57][^58][^59][^60] | 2 узла на ДЦ + 2 центральных | Сервис работает, деградируют алерты и дашборды |

## Отказ дата-центра: шаги подробно

Отказ одной AZ закрывается внутри ДЦ (п. 9.1). Отказ всего ДЦ редок, но для него есть явный план. Худший случай по емкости — отказ самого большого ДЦ, `DC-DE-FRANKFURT` (35.69% нагрузки).

| Шаг | Что происходит | Время |
| --- | -------------- | ----- |
| 1 | Monitors GTM фиксируют отказ, `DC-DE-FRANKFURT` убирается из DNS-ответов (п. 3.5) | ≈ 30 с + TTL 30 с |
| 2 | Новые подключения GTM раздает по `capacity_weight`: сначала `DC-UK-LONDON`, затем `DC-US-EAST`, остальное — по свободной емкости других ДЦ (п. 3.7) | сразу после шага 1 |
| 3 | Встречи `DC-DE-FRANKFURT` обрываются, клиенты переподключаются через `api` со случайной задержкой, чтобы не устроить шторм. Подписанный `join_token` (`meeting_id`, роль, срок) проверяется в любом ДЦ, поэтому комната пересоздается в резервном ДЦ без похода в недоступную БД | десятки секунд |
| 4 | Дежурный повышает реплику Citus `DC-DE-FRANKFURT` в `DC-UK-LONDON` до primary [^97]. Код ДЦ `de-frankfurt` из `meeting_id` начинает указывать на `DC-UK-LONDON` — в маршрутизации control plane и в GTM для имени `ws.de-frankfurt`. Запланированные встречи снова доступны | минуты, RPO — секунды |
| 5 | Чат и история участников встреч `DC-DE-FRANKFURT` недоступны до восстановления ДЦ или до восстановления из снапшотов в S3 парного ДЦ (п. 6.8) | осознанный компромисс |

**Особенность `DC-US-EAST`.** Шаги те же, реплику Citus повышают в `DC-US-WEST`. Кроме того, здесь primary `auth_pg`: логин все время работает на локальных репликах, а регистрация и правка профиля несколько минут ждут, пока дежурный повысит реплику в `DC-US-WEST` (п. 3.4).

## Хватит ли емкости

Холодный резерв ×2 не закладываем: это +100% к стоимости SFU. Вместо него на время инцидента SFU во всех ДЦ, которые принимают нагрузку, ограничивают видео профилем group «high-quality video»: 1.0/0.6 Мбит/с вместо 2.6/1.8 для 720p [^5]. Поток в запись при этом не уменьшается.

```text
трафик участника, 720p              = 2.6 + 1.8 + 0.08 + 0.15 = 4.63 Мбит/с
трафик участника, high-quality      = 1.0 + 0.6 + 0.08 + 0.15 = 1.83 Мбит/с  → 39.5% от 720p
с потоком в запись (1.88 / 10 = 0.188 Мбит/с на участника):
  720p = 4.818, high-quality = 2.018 Мбит/с                              → 41.9% от 720p
емкость SFU без DC-DE-FRANKFURT     = 100% − 35.69% = 64.31% штатной
нагрузка при профиле high-quality   = 41.9% штатного пика  <  64.31%     → помещается
```

Это верно даже при худшем допущении, что пики всех ДЦ совпали; на деле они разнесены по часовым поясам. Отказ `DC-US-EAST` проверяется так же: 41.9% < 100% − 28.84% = 71.16%.

Stateless-слои (NGINX L7, WS-поды) работают на облачных VM и подах Kubernetes и досоздаются за минуты. Но и без этого запас есть:

- **Соединения.** У 21 узла L7 вне `DC-DE-FRANKFURT` — 21.8 млн соединений при пике 16.9 млн; у 22 узлов вне `DC-US-EAST` — 22.8 млн.
- **Шторм переподключений.** 6.0 млн клиентов Франкфурта открывают новые TLS-соединения: 6 022 688 / (21 узел × 6 676 в секунду) ≈ 43 с. Поэтому клиент переподключается со случайной задержкой в пределах минуты.

## Источники

[^5]: [Zoom Support — Zoom system requirements: Zoom Web App](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0058323)

[^14]: [mediasoup Documentation — SFU overview](https://mediasoup.org/documentation/overview/)

[^15]: [AWS Route 53 Documentation — Latency-based routing](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy-latency.html)

[^16]: [Cloudflare Docs — Global traffic steering policies](https://developers.cloudflare.com/load-balancing/understand-basics/traffic-steering/steering-policies/)

[^17]: [Cloudflare Docs — Create a monitor (минимальный интервал: 60 с Pro, 15 с Business, 10 с Enterprise; consecutive_down через API)](https://developers.cloudflare.com/load-balancing/monitors/create-monitor/)

[^19]: [NGINX Community Blog — Testing the Performance of NGINX Ingress Controller for Kubernetes](https://blog.nginx.org/blog/testing-performance-nginx-ingress-controller-kubernetes)

[^20]: [NGINX Community Blog — Testing the Performance of NGINX and NGINX Plus Web Servers](https://blog.nginx.org/blog/testing-the-performance-of-nginx-and-nginx-plus-web-servers)

[^22]: [Redis Docs — Key expiration](https://redis.io/docs/latest/develop/using-commands/keyspace/)

[^23]: [Amazon S3 — Strong Consistency](https://aws.amazon.com/s3/consistency/)

[^24]: [Google Cloud Storage — Consistency](https://docs.cloud.google.com/storage/docs/consistency)

[^27]: [PostgreSQL Documentation — Replication](https://www.postgresql.org/docs/current/runtime-config-replication.html)

[^28]: [PostgreSQL Documentation — Continuous Archiving and Point-in-Time Recovery](https://www.postgresql.org/docs/current/continuous-archiving.html)

[^29]: [Citus Documentation — Choosing Distribution Column](https://docs.citusdata.com/en/stable/sharding/data_modeling.html)

[^31]: [Redis Documentation — Redis Cluster Specification](https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/)

[^32]: [PgBouncer Documentation — Features](https://www.pgbouncer.org/features.html)

[^33]: [ScyllaDB Documentation — Fault Tolerance](https://docs.scylladb.com/manual/stable/architecture/architecture-fault-tolerance.html)

[^42]: [mediasoup Documentation — RTP Parameters and Capabilities](https://mediasoup.org/documentation/v3/mediasoup/rtp-parameters-and-capabilities/)

[^46]: [Amazon S3 Documentation — Multipart upload overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)

[^54]: [Kubernetes Documentation — Overview](https://kubernetes.io/docs/concepts/overview/)

[^56]: [Prometheus Documentation — Overview](https://prometheus.io/docs/introduction/overview/)

[^57]: [Grafana Documentation — Grafana OSS and Enterprise](https://grafana.com/docs/grafana/latest/)

[^58]: [OpenTelemetry Documentation](https://opentelemetry.io/docs/)

[^59]: [Grafana Loki OSS — Log aggregation system](https://grafana.com/oss/loki/)

[^60]: [Jaeger Documentation — Introduction](https://www.jaegertracing.io/docs/latest/)

[^63]: [Kubernetes Documentation — Self-Healing](https://kubernetes.io/docs/concepts/architecture/self-healing/)

[^77]: [NGINX (F5) Blog — NGINX WebSocket Performance](https://www.f5.com/company/blog/nginx/nginx-websockets-performance)

[^80]: [ScyllaDB Documentation — Create a ScyllaDB Cluster: Multi Data Centers](https://docs.scylladb.com/manual/stable/operating-scylla/procedures/cluster-management/create-cluster-multidc.html)

[^81]: [ScyllaDB Documentation — Production Readiness Guidelines](https://docs.scylladb.com/manual/stable/operating-scylla/procedures/tips/production-readiness.html)

[^83]: [RFC 4786 — Operation of Anycast Services](https://datatracker.ietf.org/doc/html/rfc4786)

[^84]: [RFC 8445 — Interactive Connectivity Establishment (ICE)](https://datatracker.ietf.org/doc/html/rfc8445)

[^86]: [Patroni Documentation](https://patroni.readthedocs.io/en/latest/)

[^89]: [PostgreSQL Documentation — Log-Shipping Standby Servers, synchronous replication](https://www.postgresql.org/docs/current/warm-standby.html)

[^90]: [Citus Documentation — Single-Node Citus](https://docs.citusdata.com/en/stable/installation/single_node.html)

[^91]: [Linux kernel — net/netfilter/ipvs/Kconfig: запись в таблице соединений IPVS занимает 128 B, элемент хеш-таблицы — 8 B](https://github.com/torvalds/linux/blob/master/net/netfilter/ipvs/Kconfig)

[^92]: [Linux Virtual Server — Virtual Server via Direct Routing](https://www.linuxvirtualserver.org/VS-DRouting.html)

[^93]: [Keepalived Documentation — Introduction: IPVS, health checks, VRRP](https://keepalived.readthedocs.io/en/latest/introduction.html)

[^97]: [Patroni Documentation — HA multi datacenter: standby-кластер во втором ДЦ повышают вручную](https://patroni.readthedocs.io/en/latest/ha_multi_dc.html)
