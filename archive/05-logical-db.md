# 05. Логическая схема БД — обоснования

## Разделение на домены данных

| Домен | Сущности | Характер нагрузки |
|---|---|---|
| Identity | `users`, `sessions` | строгая консистентность, medium/high read |
| Community | `servers`, `rooms` | high read, medium write |
| Realtime room state | `room_participants` | very high read/write |
| Messaging | `messages` | high read/write |
| Media history | `recordings` | medium read/write |
| Observability | `analytics_events` | very high write |

## Консистентность (логический уровень)

| Сущность | Уровень | Причина |
|---|---|---|
| `users`, `sessions`, `rooms` | strong | auth и управление доступом |
| `messages`, `room_participants`, `recordings` | eventual | допустима малая задержка репликации |
| `analytics_events` | eventual | async ingestion pipeline |
