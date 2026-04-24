# 04. Локальная балансировка — расчетная часть

## Балансировка по слоям

| Слой | Протоколы | Технология |
|---|---|---|
| L4 | UDP/DTLS/SRTP | Maglev / IPVS / Envoy L4 |
| L7 | HTTPS/WSS | Nginx / Envoy |
| App routing | room -> media node | Control Plane + SFU allocator |

## Резервирование

| Контур | Формула | Примечание |
|---|---|---|
| API/L7 | `N_total = N + 1` | отказ одной ноды без деградации SLA |
| SFU pool | `N_total = N + 1` | room remap через allocator |
| Registry/state | `RF = 3, quorum >=2` | отказ одного узла хранения состояния |

## Верхнеуровневый sizing (peak)

| Параметр | Значение |
|---|---:|
| Message write peak | 29,514 RPS |
| Voice traffic peak | ~694 Gbit/s |
| RTP peak | 416,666,667 packets/s |
| RTCP peak | 1,666,668 reports/s |
