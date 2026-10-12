# Приложение 4. Локальная балансировка: ограничители и расчет

К основной части: [раздел 4](../README.md#4-локальная-балансировка-нагрузки). Номера «п. X.Y» — пункты основной части.

## Клиент за NAT и межсетевым экраном

**Клиент за NAT и межсетевым экраном.** SFU работает как ICE-Lite с публичным адресом: сам соединение не начинает, а отвечает на проверки клиента [^102]. Поэтому клиенту за NAT не нужны ни STUN, ни TURN. Если UDP закрыт, клиент подключается к тому же SFU по TCP: SFU слушает и UDP, и TCP [^102], а ICE умеет предлагать TCP-кандидаты [^103]. Не поддерживаем в MVP только сети, где прокси пропускает исключительно TLS на порт 443: для них нужен TURN по TLS.

## L4 на IPVS и межсервисная балансировка

**L4 — свой, на IPVS.** Директор принимает пакеты на VIP ДЦ и раздает TCP-соединения узлам NGINX; в режиме Direct Routing ответы идут к клиенту напрямую, мимо директора [^92]. Директоров два, active/standby: keepalived переносит VIP по VRRP и проверяет здоровье узлов NGINX [^93]. Облачный балансировщик провайдера не подходит: у самого мощного типа Selectel — 2 инстанса по 4 vCPU, до 3 Гбит/с (до 5 по заявке), а производительность HTTPS приведена для 10 000 соединений [^12]; в Kubernetes такой балансировщик создается для Service типа `LoadBalancer` [^21]. В одном нашем ДЦ одновременно до 6 млн WSS-соединений.

**Межсервисная балансировка.** gRPC-клиент получает список подов через headless Kubernetes Service и раздает вызовы round-robin [^52][^54]. Обычный L4 здесь не подходит: gRPC держит одно долгое HTTP/2-соединение, и все вызовы ушли бы в один под.

## Ограничители для расчета

| Ограничитель | Значение | Источник / расчет |
| ------------ | -------: | ----------------- |
| `LB_HTTPS_RPS` | **341 232 RPS** | NGINX Ingress Controller, HTTPS, ответ 1 KB по открытым keep-alive-соединениям, 16 CPU [^19] |
| `LB_TLS_CPS` | **6 676 новых TLS-соединений/с** | NGINX, полный TLS handshake на каждое соединение, RSA 2048, 16 CPU [^20]. С современным OpenSSL рукопожатия дешевле — значение консервативное |
| `LB_NET_GBPS` | **8.8 Gbps** | Throughput NGINX Ingress Controller; упор в 10GbE-карту стенда, а не в CPU [^19] |
| `MF_L7_MSG_SIZE` | **1 KB** | Размер ответа в RPS-тесте [^19] — средний размер сообщения API и WebSocket |
| `MF_L7_CONN_MEM` | **54 KB на WSS-соединение** | NGINX держит проксируемое WebSocket-соединение меньше чем в 20 KB: 50 000 соединений < 1 GB [^77]. Плюс до 34 KB TLS-буферов [^78]. Худший случай |
| Узел L7 | **24 vCPU / 64 GB / 100 GB SSD** | 56 GB под соединения: `56 GB / 54 KB ≈ 1.04 млн` WSS-соединений на узел |
| `IPVS_CONN_MEM` | **136 B на соединение** | Запись в таблице соединений IPVS — 128 B, элемент хеш-таблицы — 8 B [^91] |
| Узел L4 | **EL11-SSD-10GE: 6 ядер / 32 GB / 10GE** | Директор пропускает только входящий трафик (Direct Routing [^92]) |

Значения NGINX взяты для 16 CPU: в тестах это физические ядра, а облачный узел на 24 vCPU — около 12 ядер с Hyper-Threading. RPS и TLS все равно не ограничивают расчет: даже с поправкой 12/16 `N_rps` и `N_tls` в каждом ДЦ не больше `N_conn` (расчет ниже).

## Расчет количества L7

```text
MF_L7_REST_RPS  = login + create + join + leave + list + recording_meta + recording_view
                  + chat + chat_history                                                  = 51 215
MF_L7_WS_IN     = heartbeat                                                              = 675 000
MF_L7_WS_OUT    = (chat + join + leave) * (MF_MEET_SIZE - 1)                             = 328 125
MF_L7_PEAK_RPS  = MF_L7_REST_RPS + MF_L7_WS_IN + MF_L7_WS_OUT                            = 1 054 340
MF_L7_NEW_TLS   = MF_L7_REST_RPS + join                                                  = 56 424
                  # худший случай: каждый REST-запрос без keep-alive + новое WSS-соединение на каждый join
MF_L7_PEAK_GBPS = MF_L7_PEAK_RPS * 1 KB * 8 / 10^6                                       = 8.43
MF_L7_PEAK_CONN = MF_PEAK_WSS_CONNECTIONS                                                = 16 875 000

N_rps  = ceil(RPS_dc / 341 232)
N_tls  = ceil(NEW_TLS_dc / 6 676)
N_net  = ceil(GBPS_dc / 8.8)
N_conn = ceil(CONN_dc * 54 KB / 56 GB)
N_base = max(N_rps, N_tls, N_net, N_conn)

N+1 = N_base + 1
N*2 = N_base * 2
```

### Расчет по ДЦ

| ДЦ | L7 peak RPS | Новых TLS/с | L7 Gbps | WSS-соединений |
| -- | ----------: | ----------: | ------: | -------------: |
| `DC-US-EAST` | **304 072** | 16 273 | 2.43 | **4 866 750** |
| `DC-US-WEST` | **78 021** | 4 175 | 0.62 | **1 248 750** |
| `DC-BR-SAOPAULO` | **49 027** | 2 624 | 0.39 | **784 688** |
| `DC-UK-LONDON` | **42 806** | 2 291 | 0.34 | **685 125** |
| `DC-DE-FRANKFURT` | **376 294** | 20 138 | 3.01 | **6 022 688** |
| `DC-IN-MUMBAI` | **53 033** | 2 838 | 0.42 | **848 813** |
| `DC-SG-SINGAPORE` | **73 488** | 3 933 | 0.59 | **1 176 188** |
| `DC-JP-TOKYO` | **77 599** | 4 153 | 0.62 | **1 242 000** |
| **Сумма по ДЦ** | **1 054 340** | **56 424** | **8.43** | **16 875 000** |

| ДЦ | `N_rps` | `N_tls` | `N_net` | `N_conn` | `N+1` | `N*2` |
| -- | ----: | ----: | ----: | ----: | ----: | ----: |
| `DC-US-EAST` | 1 | 3 | 1 | 5 | **6** | 10 |
| `DC-US-WEST` | 1 | 1 | 1 | 2 | **3** | 4 |
| `DC-BR-SAOPAULO` | 1 | 1 | 1 | 1 | **2** | 2 |
| `DC-UK-LONDON` | 1 | 1 | 1 | 1 | **2** | 2 |
| `DC-DE-FRANKFURT` | 2 | 4 | 1 | 6 | **7** | 12 |
| `DC-IN-MUMBAI` | 1 | 1 | 1 | 1 | **2** | 2 |
| `DC-SG-SINGAPORE` | 1 | 1 | 1 | 2 | **3** | 4 |
| `DC-JP-TOKYO` | 1 | 1 | 1 | 2 | **3** | 4 |
| **Сумма по ДЦ** | **9** | **13** | **8** | **20** | **28** | **40** |

**Главный ограничитель L7 — память под одновременные WSS-соединения** (16.9 млн в пик). RPS и TLS требуют 1–4 узла на ДЦ даже без keep-alive, сеть — 1 узел, а медиа через L4 и L7 не проходит.

## Расчет количества L4

| Режим | Количество NGINX L7 | Что закладываем |
| ----- | ------------------: | --------------- |
| Рабочий вариант | **28** | `N+1` в каждом ДЦ |
| Жесткое резервирование | **40** | `N*2` в каждом ДЦ: переживает потерю AZ |

Директоры L4 считаются по памяти под таблицу соединений и по входящему трафику, плюс резервный директор:

```text
L4_RAM_dc = CONN_dc * 136 B
N_L4      = max(1, ceil(GBPS_dc / 10)) + 1        # active + standby (keepalived, VRRP)
```

| ДЦ | Соединений в таблице IPVS | Память под таблицу | Входящий трафик, Gbps (не больше) | `N` | `N+1` |
| -- | --: | --: | --: | --: | --: |
| `DC-US-EAST` | 4 866 750 | 0.66 GB | 2.43 | 1 | **2** |
| `DC-US-WEST` | 1 248 750 | 0.17 GB | 0.62 | 1 | **2** |
| `DC-BR-SAOPAULO` | 784 688 | 0.11 GB | 0.39 | 1 | **2** |
| `DC-UK-LONDON` | 685 125 | 0.09 GB | 0.34 | 1 | **2** |
| `DC-DE-FRANKFURT` | 6 022 688 | 0.82 GB | 3.01 | 1 | **2** |
| `DC-IN-MUMBAI` | 848 813 | 0.12 GB | 0.42 | 1 | **2** |
| `DC-SG-SINGAPORE` | 1 176 188 | 0.16 GB | 0.59 | 1 | **2** |
| `DC-JP-TOKYO` | 1 242 000 | 0.17 GB | 0.62 | 1 | **2** |
| **Сумма по ДЦ** | **16 875 000** | **2.29 GB** | **8.43** | **8** | **16** |

Итого **16 узлов L4** — по паре в каждом ДЦ. Даже в самом большом ДЦ таблица соединений занимает 0.82 GB из 32 GB, а входящий трафик не больше 3.01 Гбит/с при карте 10GE: второй узел нужен ради отказоустойчивости.

## Источники

[^12]: [Selectel Documentation — Cloud load balancers: типы балансировщиков и их производительность](https://docs.selectel.ru/en/cloud-servers/load-balancers/about-load-balancers/)

[^19]: [NGINX Community Blog — Testing the Performance of NGINX Ingress Controller for Kubernetes](https://blog.nginx.org/blog/testing-performance-nginx-ingress-controller-kubernetes)

[^20]: [NGINX Community Blog — Testing the Performance of NGINX and NGINX Plus Web Servers](https://blog.nginx.org/blog/testing-the-performance-of-nginx-and-nginx-plus-web-servers)

[^21]: [Kubernetes Documentation — Service type LoadBalancer](https://kubernetes.io/docs/concepts/services-networking/service/#loadbalancer)

[^52]: [gRPC Documentation — C++](https://grpc.io/docs/languages/cpp/)

[^54]: [Kubernetes Documentation — Overview](https://kubernetes.io/docs/concepts/overview/)

[^77]: [NGINX (F5) Blog — NGINX WebSocket Performance](https://www.f5.com/company/blog/nginx/nginx-websockets-performance)

[^78]: [OpenSSL Documentation — SSL_CTX_set_mode, SSL_MODE_RELEASE_BUFFERS](https://docs.openssl.org/3.5/man3/SSL_CTX_set_mode/)

[^91]: [Linux kernel — net/netfilter/ipvs/Kconfig: запись в таблице соединений IPVS занимает 128 B, элемент хеш-таблицы — 8 B](https://github.com/torvalds/linux/blob/master/net/netfilter/ipvs/Kconfig)

[^92]: [Linux Virtual Server — Virtual Server via Direct Routing](https://www.linuxvirtualserver.org/VS-DRouting.html)

[^93]: [Keepalived Documentation — Introduction: IPVS, health checks, VRRP](https://keepalived.readthedocs.io/en/latest/introduction.html)

[^102]: [mediasoup Documentation — API: WebRtcTransport (ICE Lite: транспорт не начинает ICE, а ждет ICE Binding Requests от клиента; listenInfos с протоколом udp или tcp)](https://mediasoup.org/documentation/v3/mediasoup/api/)

[^103]: [RFC 6544 — TCP Candidates with Interactive Connectivity Establishment (ICE)](https://datatracker.ietf.org/doc/html/rfc6544)
