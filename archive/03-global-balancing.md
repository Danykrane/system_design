# 03. Глобальная балансировка — обоснование

## Принцип выбора

| Критерий | Решение |
|---|---|
| Основной KPI | Минимизация RTT для media-сессий |
| DNS-стратегия | Geo/Latency DNS |
| Резервирование | Межрегиональный failover |
| Изоляция отказа | Региональная декомпозиция по DC |

## Целевое региональное покрытие

| Регион | Пример локаций | Назначение |
|---|---|---|
| NA | New York, Chicago, Los Angeles, Vancouver | Core API + SFU |
| EU | London, Frankfurt, Warsaw | Core API + SFU |
| APAC | Singapore, Tokyo, Mumbai, Manila | Core API + SFU |
| LATAM | Sao Paulo | SFU + read-replica API |
