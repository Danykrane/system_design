# Дополнительные расчеты (Discord/Zoom, WebRTC + SFU)

## Базовые метрики (с подтверждением)

| ID | Метрика | Значение | Источник |
|---|---|---:|---|
| S1 | Discord MAU | 150,000,000 | [helplama.com/discord-statistics](https://helplama.com/discord-statistics/) |
| S2 | Discord DAU | 29,000,000 | [helplama.com/discord-statistics](https://helplama.com/discord-statistics/) |
| S3 | Сообщений в день | 850,000,000 | [venturebeat.com](https://venturebeat.com/business/discord-crosses-250-million-users-as-it-hits-4-year-anniversary/) |
| S4 | Минут голосовых разговоров в день | 4,000,000,000 | [cloudwards.net/discord-statistics](https://www.cloudwards.net/discord-statistics/) |
| S5 | Пиковый online (concurrent users) | 8,200,000 | [cloudwards.net/discord-statistics](https://www.cloudwards.net/discord-statistics/) |
| S6 | Исторический voice peak (Discord, 2018) | 2,600,000 пользователей, 220 Gbit/s | [habr.com/ru/articles/423171](https://habr.com/ru/articles/423171/) |

## Производные расчеты

| ID | Формула | Результат |
|---|---|---:|
| D1 | Сообщений на DAU: `S3 / S2` | `29.31` сообщений/польз./день |
| D2 | RPS отправки сообщений: `S3 / 86400` | `9,838` RPS |
| D3 | Средний concurrent voice users: `S4 / (24*60)` | `2,777,778` |
| D4 | Voice peak коэффициент: `S5 / D3` | `2.95` |
| D5 | Битрейт на 1 активного voice user: `220 Gbit/s / 2,600,000` | `84.6 Kbit/s` |
| D6 | Средний voice-трафик: `D3 * D5` | `~235 Gbit/s` |
| D7 | Пиковый voice-трафик: `S5 * D5` | `~694 Gbit/s` |
| D8 | RTP packets/s (20 ms): `(S4*60)/(86400*0.02)` | `138,888,889 packets/s` |
| D9 | RTCP reports/s (каждые 5 сек): `(S4*60)/(86400*5)` | `555,556 reports/s` |
| D10 | RPS авторизации (1 вход на DAU в день): `S2 / 86400` | `336 RPS` |

## Примечание

- Все метрики `D*` получены только из подтвержденных метрик `S*`.
- Для профилей качества видео (720p/1080p) в `README.md` использованы официальные требования Zoom по пропускной способности.
