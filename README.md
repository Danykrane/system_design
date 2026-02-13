# Discord-подобный сервис: голос/видеозвонки real-time (WebRTC + SFU)

> **Формат:** расчётно‑пояснительная записка в `README.md` (Markdown).  
> **Фокус MVP:** voice/video для каналов сообществ (guild/server → voice channel), медиатрафик через SFU, сигналинг через WS/HTTP.

---

## TL;DR
Проектируется подсистема **голосовых/видео‑сессий**:
1) пользователь заходит в голосовой канал  
2) идёт сигналинг (WS/HTTP) и ICE‑согласование  
3) медиа идёт по UDP/SRTP через **SFU** (селективная ретрансляция), чтобы выдерживать многопользовательские комнаты.

---

## 1. Тема и целевая аудитория

### 1.1 Тип сервиса
Массовый B2C сервис (desktop + mobile + web). Существенная логика на бэкенде: сигналинг, распределение по регионам, NAT traversal (ICE/STUN/TURN), медиасерверы (SFU), мониторинг качества, failover.

### 1.2 Тема
**Real‑time voice/video calls** в “серверной” модели (guild → voice channel):
- многопользовательский voice,
- video в комнате (несколько активных видео),
- screen share (упрощённо),
- low latency + устойчивость в плохих сетях.

Ключевая ставка: **SFU вместо P2P‑mesh** (иначе в больших комнатах клиентский аплинк/даунлинк “взрывается”).

### 1.3 Реальные аналоги и ниша
- **Discord** — основной аналог (voice/video в сообществах), публично указывает “200M+ monthly active users”.
- B2B аналоги по технологии: Zoom / Teams / Slack Huddles (подтверждают рынок real‑time calls).

### 1.4 Целевая аудитория
Для учебного проекта фиксируем целевую нагрузку:
- **MAU:** 50,000,000 / месяц (глобально)
- **DAU:** 10,000,000 / день (глобально)
- **Пиковая одновременная аудитория (цель):**
  - Voice CCU ≈ 510,417
  - Video CCU ≈ 55,556
  - Screen share CCU ≈ 13,333

Регионы (для будущей геораскладки ДЦ):
- Северная Америка 40%, Европа 35%, Азия 20%, прочие 5%.

---

## 1.5 MVP: ключевой функционал

1) **Auth + device sessions** (JWT/refresh).  
2) **Join voice channel**: выбрать регион/endpoint, получить ICE‑конфиг, токен и параметры сессии.  
3) **Сигналинг (WebSocket)**: SDP/ICE, voice‑state (join/leave), speaking indicator.  
4) **Voice через SFU**: Opus, одна отправка от клиента → ретрансляция/маршрутизация на сервере.  
5) **Video в комнате**: включить/выключить камеру, несколько потоков через SFU.  
6) **Screen share (упрощённо)**: 1 стример → N зрителей внутри канала.  
7) **Надёжность сессии**: reconnect и (при необходимости) failover на другой voice‑server.

**Вне MVP:** запись звонков, хранение медиа, “улучшайзеры” звука, монетизация, SDK/боты.

---

# 2. Расчёт нагрузки

## 2.1 Входные допущения

### Аудитория и вовлечённость
- **DAU = 10,000,000**
- Доля пользователей, которые заходят в voice‑каналы в день: **35%** → **3,500,000** unique/day  
- Доля пользователей, которые используют video в день: **8%** → **800,000** unique/day  
- Доля пользователей, которые включают screen share в день: **2%** → **200,000** unique/day  

### Действия (в день)
- Среднее число **join voice channel** на voice‑пользователя: **4**  
- Среднее время в voice на voice‑пользователя: **30 мин/день**  
- Среднее время в video на video‑пользователя: **10 мин/день**  
- Среднее время screen share на share‑пользователя: **8 мин/день**

### Пиковость
- Для событий (join/signaling) берём **PeakFactor = 10** (вечерние пики).  
- Для CCU:
  - voice: **×7**
  - video: **×10**
  - share: **×12**

> Эти числа — явные гипотезы. Все метрики масштабируются линейно от DAU и коэффициентов вовлечённости.

---

## 2.2 Продуктовые метрики

| Метрика | Значение | Как получено |
|---|---:|---|
| MAU | 50,000,000 / мес | целевой масштаб клона |
| DAU | 10,000,000 / день | целевой масштаб клона |
| Voice unique users/day | 3,500,000 | DAU × 35% |
| Total voice minutes/day | 105,000,000 мин | voice_users × 30 |
| Avg Voice CCU | 72,917 | voice_minutes_day / 1440 |
| **Peak Voice CCU** | **510,417** | avg × 7 |
| Video unique users/day | 800,000 | DAU × 8% |
| Total video minutes/day | 8,000,000 мин | video_users × 10 |
| Avg Video CCU | 5,556 | video_minutes_day / 1440 |
| **Peak Video CCU** | **55,556** | avg × 10 |
| Screen share unique users/day | 200,000 | DAU × 2% |
| Total share minutes/day | 1,600,000 мин | share_users × 8 |
| Avg Share CCU | 1,111 | share_minutes_day / 1440 |
| **Peak Share CCU** | **13,333** | avg × 12 |
| Voice joins/day | 14,000,000 | voice_users × 4 |

---

## 2.3 Размер хранилища

> В MVP **медиа не хранится** (нет записи). Храним: профили/сессии, журналы сессий, QoE‑телеметрию (агрегаты), конфиги.

### 2.3.1 Средний размер хранилища на пользователя
| Тип данных | Единица | Оценка | Комментарий |
|---|---|---:|---|
| User profile + settings | bytes/user | ~7 KB | базовые поля + настройки |
| Voice join log | bytes/join | ~300 B | session_id, channel_id, region, timestamps, result |
| QoE report (агрегат) | bytes/min | ~120 B | jitter, loss, rtt, bitrate (сжатый JSON/Protobuf) |

### 2.3.2 Итого по системе
| Блок | Объём | Как получено |
|---|---:|---|
| User metadata | 325.96 GB | MAU × 7KB |
| Voice join logs (30 дней) | 117.35 GB | joins/day × 300B × 30 |
| QoE telemetry (14 дней) | 164.29 GB | voice_minutes/day × 120B × 14 |
| **Итого** | **607.59 GB (~0.59 TB)** | сумма |

> Вывод: по storage сервис относительно “лёгкий”; **основная стоимость — сеть и медиасерверы**.

---

## 2.4 Технические метрики: RPS и сеть

### 2.4.1 RPS по основным запросам (HTTP + WS)

Формулы:
- `RPS_avg = Requests_per_day / 86400`
- `RPS_peak ≈ RPS_avg × PeakFactor`

| Тип запроса | Requests/day | RPS avg | RPS peak | Примечание |
|---|---:|---:|---:|---|
| `POST /voice/join` | 14,000,000 | 162.0 | 1,620 | вход в voice‑канал |
| `POST /voice/leave` | 14,000,000 | 162.0 | 1,620 | выход (≈ join) |
| WS signaling msgs | 140,000,000 | 1,620 | 16,204 | SDP/ICE/state; ~10 msg/join |
| `POST /qoe/report` (батч 1/мин) | 105,000,000 | 1,215 | 8,507 | качество связи |

> Важно: медиапакеты RTP/RTCP **не считаем** как “RPS”, это отдельный UDP‑трафик (см. ниже).

---

### 2.4.2 Сетевой трафик

#### A) Media traffic (основной)
Принятые битрейты (на проводе, приблизительно):
- Voice: **50 kbps up + 50 kbps down** на пользователя в канале (Opus + overhead)
- Video (среднее): **0.6 Mbps up + 0.9 Mbps down** на video‑пользователя (адаптивно, ограничение числа получаемых потоков)
- Screen share: **2.0 Mbps** на stream; в пике считаем **10% senders / 90% viewers**

##### Пиковая пропускная способность (Gbps)
| Блок | Peak ingress (Gbps) | Peak egress (Gbps) |
|---|---:|---:|
| Voice | 25.52 | 25.52 |
| Video | 33.33 | 50.00 |
| Screen share | 2.67 | 24.00 |
| **ИТОГО (media)** | **61.52** | **99.52** |

#### B) Media traffic (суточный объём, по средним)
| Направление | Объём |
|---|---:|
| Ingress media (GB/day) | 77,775 |
| Egress media (GB/day) | 114,975 |

> Для расчёта стоимости хостинга обычно важнее **egress**.

#### C) Signaling traffic (оценка, суточный)
Гипотезы:
- `POST /voice/join` ≈ 3 KB (request+response)
- WS signaling msg ≈ 1 KB
- QoE report ≈ 0.5 KB

| Блок | Объём (GB/day) |
|---|---:|
| HTTP join+leave | 80.11 |
| WS signaling | 133.51 |
| QoE reports | 50.07 |

> Вывод: signaling трафик **на порядки меньше**, чем медиа.

---

## 2.5 Что дальше по заданию
- В глобальной балансировке (GeoDNS/Anycast) ключевое — **latency** и стоимость egress.
- В локальной балансировке считать не только L7 RPS, но и **UDP capacity** на медиасерверах.
- Для БД: основная нагрузка — QoE/логирование/конфиги; можно разнести OLTP (Postgres) и time‑series (ClickHouse/TSDB).

---

## Источники
1. Discord — “About Discord / company: 200M+ monthly active users”. https://discord.com/company  
2. Discord Engineering Blog — “How Discord Handles Two and Half Million Concurrent Voice Users using WebRTC”. https://discord.com/blog/how-discord-handles-two-and-half-million-concurrent-voice-users-using-webrtc  
3. Discord Developer Docs — “Voice Connections (DAVE / E2EE), only E2EE calls starting March 1st, 2026”. https://discord.com/developers/docs/topics/voice-connections  
4. Discord Support — “Minimum Client Version Requirements for Voice Chat” (DAVE requirement after March 1, 2026). https://support.discord.com/hc/en-us/articles/38025123604631-Minimum-Client-Version-Requirements-for-Voice-Chat  
5. W3C — WebRTC specification. https://www.w3.org/TR/webrtc/  
6. NGINX Blog — “Testing the Performance of NGINX Ingress Controller for Kubernetes”. https://blog.nginx.org/blog/testing-performance-nginx-ingress-controller-kubernetes  
7. NGINX Blog — “Testing the Performance of NGINX and NGINX Plus Web Servers”. https://blog.nginx.org/blog/testing-the-performance-of-nginx-and-nginx-plus-web-servers  
8. LiveKit — “Bitrate Guide for WebRTC Video”. https://livekit.io/webrtc/bitrate-guide  
