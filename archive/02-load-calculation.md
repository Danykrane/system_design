# 02. Расчет нагрузки — формулы и промежуточные вычисления

## Подтвержденные входные параметры

| ID | Параметр | Значение | Источник |
|---|---|---:|---|
| S1 | DAU | 29,000,000 | [1] |
| S2 | Messages/day | 850,000,000 | [3] |
| S3 | Voice minutes/day | 4,000,000,000 | [4] |
| S4 | Concurrent peak users | 8,200,000 | [4] |
| S5 | Historical voice peak throughput | 220 Gbit/s at 2.6M users | [9] |

## Производные метрики

| ID | Формула | Результат |
|---|---|---:|
| D1 | `S2 / S1` | `29.31` messages/user/day |
| D2 | `S2 / 86400` | `9,838` RPS |
| D3 | `S3 / 1440` | `2,777,778` avg concurrent voice users |
| D4 | `S4 / D3` | `2.95` peak factor |
| D5 | `220 Gbit/s / 2,600,000` | `84.6 Kbit/s` per active voice user |
| D6 | `D3 * D5` | `~235 Gbit/s` avg voice traffic |
| D7 | `S4 * D5` | `~694 Gbit/s` peak voice traffic |
| D8 | `(S3*60)/(86400*0.02)` | `138,888,889` RTP packets/s |
| D9 | `(S3*60)/(86400*5)` | `555,556` RTCP reports/s |
