# 11. Расчет ресурсов — развернутый sizing

## Входные величины

| Параметр | Значение |
|---|---:|
| DAU | 29,000,000 |
| Peak concurrent users | 8,200,000 |
| Peak message write | 29,514 RPS |
| Peak voice traffic | ~694 Gbit/s |

## Приближенный расчет по пулам

| Пул | Подход к sizing | Запас |
|---|---|---|
| Edge/L4-L7 | от peak traffic + TLS termination | `+30%` |
| SFU pool | от concurrent media users | `+35%` |
| API/core services | от peak RPS + p95 latency budget | `+30%` |
| Databases | от write/read throughput + replication | `N+1` на AZ |
| Observability | от ingest rate logs/metrics/traces | `+25%` |

## Проверка на отказ домена

| Сценарий | Правило |
|---|---|
| Падение 1 AZ | remaining AZ должны удержать не менее 60% peak |
| Падение 1 SFU узла | активные комнаты переразмещаются без полной потери аудио |
