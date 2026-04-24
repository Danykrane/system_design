# 08. Технологии — обоснование стека

| Слой | Выбор | Почему подходит под highload calls |
|---|---|---|
| Realtime/backend | Go/C++/Rust | предсказуемая производительность и сетевые примитивы |
| Frontend | React + TypeScript | быстрый UI-цикл и контроль типов |
| Edge/API gateway | Nginx/Envoy | зрелая L7-маршрутизация, TLS, observability |
| Orchestration | Kubernetes | auto-healing и горизонтальное масштабирование |
| Metrics/logs/traces | Prometheus + Grafana + Loki + Jaeger | полный контур мониторинга и дебага |

## Trade-off (коротко)

| Решение | Плюс | Минус |
|---|---|---|
| C++/Rust на media path | latency и контроль ресурсов | выше сложность разработки |
| K8s | удобная эксплуатация и HPA | operational overhead |
