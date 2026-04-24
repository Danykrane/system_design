# 10. Схема проекта — пояснения к блокам

## Логика потоков

| Поток | Маршрут |
|---|---|
| Auth/Signaling | Client -> DNS/LB -> API Gateway -> Auth/Session -> Room control |
| Media | Client -> Anycast/LB -> SFU -> Recipient clients |
| Messaging | Client -> Gateway -> Message service -> Storage + fan-out |
| Analytics | Services -> Kafka -> ClickHouse |

## Границы контуров

| Контур | SLA приоритезация |
|---|---|
| Core user flow (auth + signaling + media) | highest |
| Messaging history | high |
| Analytics and BI | medium/low |
