#!/usr/bin/env python3
"""Единая модель расчёта MeetFlow.

Все числа в README (разделы 2-6 и 11) получены этим скриптом, поэтому
при изменении любого допущения (например, MF_K_PEAK) достаточно поменять
константу и перезапустить:

    python3 resource/calc/meetflow_calc.py > /tmp/meetflow_tables.md

Единицы: десятичные (1 KB = 10^3 B, 1 GB = 10^9 B, 1 Gbps = 10^9 бит/с).
"""

import math

# ---------------------------------------------------------------- 2. Исходные метрики
MAU = 320_000_000            # Teams, FY24 Q1 [^1]
DAU = 115_000_000            # Teams, 10.2020 [^2]
DMP = 300_000_000            # участий во встречах в сутки, Zoom 04.2020 [^3]
MEET_SIZE = 10               # участников в средней встрече [^4]
MEET_LEN_MIN = 54            # минут в средней встрече [^4]
V_UP, V_DOWN = 2.6, 1.8      # Мбит/с, 720p group video up/down [^5]
V_UP_HQ, V_DOWN_HQ = 1.0, 0.6  # Мбит/с, group "high-quality video" up/down [^5]
AUDIO, SCREEN = 0.08, 0.15   # Мбит/с, VoIP и screen sharing upper-bound [^5]
HB_SEC = 25                  # интервал heartbeat, Socket.IO pingInterval [^9]
K = 1.5                      # MF_K_PEAK — суточный пик к среднему (замечание ревьюера)
K_OLD = 3                    # значение в прошлой версии работы

# Проектные допущения (вынесены в раздел 2, раньше были разбросаны по 5.2/6.6)
CHAT_PER_JOIN = 5            # сообщений чата на одно участие
CHAT_MSG_B = 1_000           # средний размер сообщения (лимит 4 000 символов [^6])
LIST_PER_DAU = 3             # открытий списка встреч на DAU в сутки
LOGIN_PER_DAU = 1            # созданий сессии (логинов) на DAU в сутки

DAY = 86_400


def peak(per_day):
    return per_day / DAY * K


# ---------------------------------------------------------------- 2.2 продуктовые
MEETINGS_DAY = DMP / MEET_SIZE
PART_MIN_DAY = DMP * MEET_LEN_MIN
AVG_ONLINE = PART_MIN_DAY / 1440
PEAK_ONLINE = AVG_ONLINE * K                  # = пиковое число WSS-соединений
AVG_MEETINGS_ONLINE = AVG_ONLINE / MEET_SIZE
PEAK_MEETINGS_ONLINE = PEAK_ONLINE / MEET_SIZE
HB_DAY = PART_MIN_DAY * 60 / HB_SEC
CHAT_DAY = DMP * CHAT_PER_JOIN
LIST_DAY = DAU * LIST_PER_DAU
LOGIN_DAY = DAU * LOGIN_PER_DAU

# ---------------------------------------------------------------- 2.3 хранение
REC_SIZE_GB = (V_DOWN + AUDIO) * MEET_LEN_MIN * 60 / 8 / 1000
REC_PB_DAY = MEETINGS_DAY * REC_SIZE_GB / 1e6
REC_PB_30D = REC_PB_DAY * 30
CHAT_TB_30D = CHAT_DAY * 30 * CHAT_MSG_B / 1e12
USERS_GB = MAU * 256 / 1e9
MEET_META_GB = MEETINGS_DAY * 30 * 256 / 1e9
INVITES_GB = MEETINGS_DAY * 30 * 128 / 1e9
PARTICIPANTS_TB = DMP * 30 * 128 / 1e12
USER_MEETINGS_TB = DMP * 30 * 128 / 1e12
SESSIONS_GB = DAU * 128 / 1e9

# ---------------------------------------------------------------- 2.4 трафик и RPS
BW_AVG = {  # Гбит/с, средний
    "Video upload": AVG_ONLINE * V_UP / 1000,
    "Video download": AVG_ONLINE * V_DOWN / 1000,
    "Audio VoIP": AVG_ONLINE * AUDIO / 1000,
    "Screen sharing upper-bound": AVG_ONLINE * SCREEN / 1000,
}
REC_STREAM_AVG = AVG_MEETINGS_ONLINE * (V_DOWN + AUDIO) / 1000  # SFU -> recording, worst-case
MEDIA_PEAK = sum(BW_AVG.values()) * K
REC_STREAM_PEAK = REC_STREAM_AVG * K
SFU_PEAK = MEDIA_PEAK + REC_STREAM_PEAK

EVENTS_DAY = {  # метод -> событий в сутки
    "POST /auth/login": LOGIN_DAY,
    "POST /meetings": MEETINGS_DAY,
    "POST /meetings/{id}/join": DMP,
    "POST /meetings/{id}/leave": DMP,
    "WS /presence/heartbeat": HB_DAY,
    "POST /meeting-chat/messages": CHAT_DAY,
    "GET /users/{id}/meetings?limit=100": LIST_DAY,
    "POST /recordings/metadata": MEETINGS_DAY,
}
RPS = {k: peak(v) for k, v in EVENTS_DAY.items()}
R_LOGIN = RPS["POST /auth/login"]
R_CREATE = RPS["POST /meetings"]
R_JOIN = RPS["POST /meetings/{id}/join"]
R_LEAVE = RPS["POST /meetings/{id}/leave"]
R_HB = RPS["WS /presence/heartbeat"]
R_CHAT = RPS["POST /meeting-chat/messages"]
R_LIST = RPS["GET /users/{id}/meetings?limit=100"]
R_REC = RPS["POST /recordings/metadata"]

# ---------------------------------------------------------------- 3.2 ДЦ
# Шаг 1: страны из SimilarWeb [^12]; шаг 2: Other разложен по макрорегионам.
US, JP, IN, UK, CA = 40.73, 5.00, 4.35, 3.72, 3.69
OTHER = 100 - (US + JP + IN + UK + CA)               # 42.51
LATAM = 7.5                                          # допущение: каждая страна LatAm < 3.69%
LATAM_NORTH = 2.5                                    # Мексика, Центр. Америка, Карибы (~1/3 населения LatAm)
LATAM_SOUTH = LATAM - LATAM_NORTH                    # Южная Америка
REV_AMER, REV_APAC, REV_EMEA = 72.1, 12.1, 15.8      # выручка Zoom FY2026 по регионам, % [^72]
INTL = 100 - (US + CA) - LATAM                       # EMEA + APAC целиком
APAC_TOTAL = INTL * REV_APAC / (REV_APAC + REV_EMEA)
EMEA_TOTAL = INTL * REV_EMEA / (REV_APAC + REV_EMEA)
APAC_REST = APAC_TOTAL - JP - IN
EMEA_REST = EMEA_TOTAL - UK
US_WEST_POP = 23.7                                   # доля населения West по Census 2020 [^73]

DC = {  # ДЦ -> доля нагрузки, %
    "DC-US-EAST": US * (100 - US_WEST_POP) / 100 + CA + LATAM_NORTH,
    "DC-US-WEST": US * US_WEST_POP / 100,
    "DC-BR-SAOPAULO": LATAM_SOUTH,
    "DC-UK-LONDON": UK,
    "DC-DE-FRANKFURT": EMEA_REST,
    "DC-IN-MUMBAI": IN,
    "DC-SG-SINGAPORE": APAC_REST,
    "DC-JP-TOKYO": JP,
}
assert abs(sum(DC.values()) - 100) < 1e-9

# ---------------------------------------------------------------- 4. L7 NGINX
L7_HTTPS_RPS = 342_785       # NGINX Ingress, 24 CPU, HTTPS RPS 1 KB [^19]
L7_TLS_CPS = 10_274          # новые HTTPS-соединения (TLS handshake)/с, 24 CPU [^20]
L7_NET_GBPS = 8.8            # throughput NGINX Ingress [^19]
L7_REQ_B = 1_000
WS_CONN_B = 20_000           # NGINX держит WS-соединение (клиент+upstream) в < 20 KB [^77]
TLS_BUF_B = 34_000           # буферы TLS, если не освобождены (SSL_MODE_RELEASE_BUFFERS) [^78]
L7_CONN_B = WS_CONN_B + TLS_BUF_B
L7_NODE_RAM_GB, L7_RAM_RESERVED_GB = 64, 8

REST_RPS = R_LOGIN + R_CREATE + R_JOIN + R_LEAVE + R_LIST + R_REC + R_CHAT
WS_IN = R_HB
WS_OUT = (R_CHAT + R_JOIN + R_LEAVE) * (MEET_SIZE - 1)   # доставка чата и presence-событий
L7_RPS = REST_RPS + WS_IN + WS_OUT
L7_NEW_TLS = (R_LOGIN + R_CREATE + R_JOIN + R_LEAVE + R_LIST + R_REC) + R_JOIN  # REST без keep-alive + WSS connect
L7_GBPS = L7_RPS * L7_REQ_B * 8 / 1e9
CONN_PER_L7 = (L7_NODE_RAM_GB - L7_RAM_RESERVED_GB) * 1e9 / L7_CONN_B

# ---------------------------------------------------------------- 11. нормативы
JITSI_MBPS, JITSI_CPU, JITSI_CORES = 550.4, 0.203, 4   # [^74]
CORE_GBPS = JITSI_MBPS / (JITSI_CPU * JITSI_CORES) / 1000
CPU_TARGET = 0.7
SFU_CORES = 6                                         # EL11-SSD-10GE [^66]
SFU_NODE_GBPS = min(10.0, SFU_CORES * CORE_GBPS * CPU_TARGET)

WS_POD_CONN = int(6e9 / WS_CONN_B)    # под 4 CPU / 8 GB, 6 GB под соединения
AUTH_POD_RPS, CP_POD_RPS, CHAT_POD_RPS = 1_000, 1_500, 5_000
NODE_CORES_USABLE = 12                # CL34-NVMe: 14 ядер, 2 под ОС/kubelet
REDIS_SHARD_OPS = 120_000             # [^79]
SCYLLA_NODE_TB = 1.0                  # CL34-NVMe 2x1 TB, <= 50% заполнения

AUTH_RPS = R_LOGIN + R_CREATE + R_JOIN
CP_RPS = R_CREATE + R_JOIN + R_LEAVE + R_LIST + R_REC
RUNTIME_OPS = R_HB + R_JOIN + R_LEAVE + R_CREATE + R_CHAT
SESSION_OPS = (R_CREATE + R_JOIN + R_LIST) + R_LOGIN

PRICE = {
    "k8s": 15_532.36, "l4": 3_944.59, "el11": 14_000, "cl34": 13_600, "bl18": 34_900,
    "s3_gb": 0.81,
    "vcpu": 668.35, "ram_gb": 243.04, "ssd_gb": 9.53,
}
L7_NODE_PRICE = 24 * PRICE["vcpu"] + L7_NODE_RAM_GB * PRICE["ram_gb"] + 100 * PRICE["ssd_gb"]
USD = 80

# DR-пары для асинхронной реплики Citus (кто хранит реплику чьего кластера)
DR_HOST = {
    "DC-US-EAST": "DC-US-WEST", "DC-US-WEST": "DC-US-EAST", "DC-BR-SAOPAULO": "DC-US-EAST",
    "DC-UK-LONDON": "DC-DE-FRANKFURT", "DC-DE-FRANKFURT": "DC-UK-LONDON",
    "DC-IN-MUMBAI": "DC-SG-SINGAPORE", "DC-SG-SINGAPORE": "DC-JP-TOKYO",
    "DC-JP-TOKYO": "DC-SG-SINGAPORE",
}
AUTH_PRIMARY_DC = "DC-US-EAST"


def ceil(x):
    return int(math.ceil(x - 1e-9))


def per_dc():
    rows = {}
    for d, share in DC.items():
        s = share / 100
        r = {"share": share}
        r["conn"] = PEAK_ONLINE * s
        r["l7_rps"] = L7_RPS * s
        r["l7_tls"] = L7_NEW_TLS * s
        r["l7_gbps"] = L7_GBPS * s
        r["n_rps"] = ceil(r["l7_rps"] / L7_HTTPS_RPS)
        r["n_tls"] = ceil(r["l7_tls"] / L7_TLS_CPS)
        r["n_net"] = ceil(r["l7_gbps"] / L7_NET_GBPS)
        r["n_conn"] = ceil(r["conn"] / CONN_PER_L7)
        r["l7_base"] = max(r["n_rps"], r["n_tls"], r["n_net"], r["n_conn"])
        r["l7"] = r["l7_base"] + 1
        r["l7_x2"] = r["l7_base"] * 2
        r["sfu_gbps"] = SFU_PEAK * s
        r["sfu"] = ceil(r["sfu_gbps"] / SFU_NODE_GBPS) + 1
        r["rec_gbps"] = REC_STREAM_PEAK * s
        r["rec"] = ceil(r["rec_gbps"] / SFU_NODE_GBPS) + 1
        r["auth"] = ceil(AUTH_RPS * s / AUTH_POD_RPS) + 1
        r["cp"] = ceil(CP_RPS * s / CP_POD_RPS) + 1
        r["ws"] = ceil(r["conn"] / WS_POD_CONN) + 1
        r["chat"] = ceil(R_CHAT * s / CHAT_POD_RPS) + 1
        r["pgb"] = 3
        r["app_cpu"] = 4 * (r["auth"] + r["cp"] + r["ws"] + r["chat"]) + 2 * r["pgb"]
        r["app_ram"] = 8 * (r["auth"] + r["cp"] + r["ws"] + r["chat"]) + 2 * r["pgb"]
        r["app_nodes"] = ceil(r["app_cpu"] / NODE_CORES_USABLE) + 1
        r["runtime_ops"] = RUNTIME_OPS * s
        r["runtime_masters"] = max(3, ceil(r["runtime_ops"] / REDIS_SHARD_OPS))
        r["redis_nodes"] = r["runtime_masters"]  # перекрёстная схема: на узле master + replica
        r["auth_pg"] = 2 if d == AUTH_PRIMARY_DC else 1
        r["citus"] = 2 + sum(1 for v in DR_HOST.values() if v == d)
        r["scylla_meet_tb"] = 3 * (PARTICIPANTS_TB * s + USER_MEETINGS_TB)
        r["scylla_meet"] = max(3, ceil(r["scylla_meet_tb"] / SCYLLA_NODE_TB))
        r["scylla_chat_tb"] = 3 * CHAT_TB_30D * s
        r["scylla_chat"] = max(3, ceil(r["scylla_chat_tb"] / SCYLLA_NODE_TB))
        r["obs"] = 2 + (2 if d == AUTH_PRIMARY_DC else 0)
        r["s3_pb"] = REC_PB_30D * s
        rows[d] = r
    return rows


def fmt(x, nd=0):
    return f"{x:,.{nd}f}".replace(",", " ")


def b(x):
    return f"**{x}**"


def table(head, rows, align=None):
    align = align or ["---"] * len(head)
    out = ["| " + " | ".join(head) + " |", "| " + " | ".join(align) + " |"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def totals(p):
    keys = [k for k in next(iter(p.values())) if k != "share"]
    return {k: sum(r[k] for r in p.values()) for k in keys}


def servers_dc(r):
    return (r["sfu"] + r["rec"] + r["l7"] + r["app_nodes"] + r["redis_nodes"] + r["auth_pg"] + r["citus"]
            + r["scylla_meet"] + r["scylla_chat"] + r["obs"])


def cost_lines(tot, sfu_n=None, rec_n=None):
    n_dc = len(DC)
    return [
        ("Kubernetes-кластер/3 зоны доступности", n_dc, PRICE["k8s"]),
        ("L4-балансировщик", n_dc, PRICE["l4"]),
        ("Ingress L7 (NGINX)", tot["l7"], L7_NODE_PRICE),
        ("Kubernetes app pool", tot["app_nodes"], PRICE["cl34"]),
        ("Пул SFU (медиа)", tot["sfu"] if sfu_n is None else sfu_n, PRICE["el11"]),
        ("Воркеры записи", tot["rec"] if rec_n is None else rec_n, PRICE["el11"]),
        ("Redis (session + runtime)", tot["redis_nodes"], PRICE["cl34"]),
        ("PostgreSQL auth_pg", tot["auth_pg"], PRICE["bl18"]),
        ("PostgreSQL + Citus (meeting_pg + recording_pg)", tot["citus"], PRICE["bl18"]),
        ("ScyllaDB meeting_scylla", tot["scylla_meet"], PRICE["cl34"]),
        ("ScyllaDB chat_scylla", tot["scylla_chat"], PRICE["cl34"]),
        ("Объектное хранилище S3", REC_PB_30D * 1e6, PRICE["s3_gb"]),
        ("Наблюдаемость", tot["obs"], PRICE["cl34"]),
    ]


def main():
    p = per_dc()
    tot = totals(p)
    sh = {d: r["share"] / 100 for d, r in p.items()}

    print("<!-- 3.3 продуктовая нагрузка -->")
    rows = [[f"`{d}`", f"{r['share']:.2f}%", b(fmt(DAU*sh[d])), b(fmt(DMP*sh[d])), b(fmt(MEETINGS_DAY*sh[d])),
             b(fmt(PEAK_ONLINE*sh[d]))] for d, r in p.items()]
    rows.append(["**Итого**", "**100%**", b(fmt(DAU)), b(fmt(DMP)), b(fmt(MEETINGS_DAY)), b(fmt(PEAK_ONLINE))])
    print(table(["ДЦ", "Доля", "DAU", "Участий/сутки", "Встреч/сутки", "Peak online = WSS-соединений"], rows,
                ["--", "---:", "--:", "------------:", "-----------:", "----------:"]))

    print("\n<!-- 3.3 пиковый RPS -->")
    keys = ["POST /auth/login", "POST /meetings", "POST /meetings/{id}/join", "POST /meetings/{id}/leave",
            "WS /presence/heartbeat", "POST /meeting-chat/messages", "GET /users/{id}/meetings?limit=100",
            "POST /recordings/metadata"]
    short = ["`login`", "`create`", "`join`", "`leave`", "`heartbeat`", "`chat`", "`list`", "`recording meta`"]
    rows = [[f"`{d}`"] + [b(fmt(RPS[k_]*sh[d])) for k_ in keys] for d in p]
    rows.append(["**Итого**"] + [b(fmt(RPS[k_])) for k_ in keys])
    print(table(["ДЦ"] + short, rows, ["--"] + ["--:"] * len(keys)))

    print("\n<!-- 3.3 пиковый media bandwidth -->")
    rows = []
    for d in p:
        vals = [v * K * sh[d] for v in BW_AVG.values()]
        rows.append([f"`{d}`"] + [b(fmt(v, 1) + " Gbps") for v in vals] + [b(fmt(sum(vals), 1) + " Gbps"),
                     fmt(REC_STREAM_PEAK*sh[d], 1) + " Gbps"])
    vals = [v * K for v in BW_AVG.values()]
    rows.append(["**Итого**"] + [b(fmt(v, 2) + " Gbps") for v in vals] + [b(fmt(sum(vals), 2) + " Gbps"),
                 b(fmt(REC_STREAM_PEAK, 1) + " Gbps")])
    print(table(["ДЦ", "Video upload", "Video download", "Audio", "Screen sharing", "Media суммарно", "SFU → запись"],
                rows, ["--"] + ["-----------:"] * 6))

    print("\n<!-- 3.3 записи -->")
    rows = [[f"`{d}`", b(f"{REC_PB_DAY*sh[d]:.3f} PB/сутки"), b(f"{REC_PB_30D*sh[d]:.2f} PB")] for d in p]
    rows.append(["**Итого**", b(f"{REC_PB_DAY:.3f} PB/сутки"), b(f"{REC_PB_30D:.2f} PB")])
    print(table(["ДЦ", "Worst-case запись/сутки", "Worst-case запись за 30 дней"], rows, ["--", "------:", "------:"]))

    print("\n<!-- 4.5 L7 нагрузка -->")
    rows = [[f"`{d}`", b(fmt(r["l7_rps"])), fmt(r["l7_tls"]), f"{r['l7_gbps']:.2f}", b(fmt(r["conn"]))] for d, r in p.items()]
    rows.append(["**Сумма по ДЦ**", b(fmt(tot["l7_rps"])), b(fmt(tot["l7_tls"])), b(f"{tot['l7_gbps']:.2f}"), b(fmt(tot["conn"]))])
    print(table(["ДЦ", "L7 peak RPS", "Новых TLS/с", "L7 Gbps", "WSS-соединений"], rows, ["--", "----------:", "----------:", "------:", "-------------:"]))
    print()
    rows = [[f"`{d}`", r["n_rps"], r["n_tls"], r["n_net"], r["n_conn"], b(r["l7"]), r["l7_x2"]] for d, r in p.items()]
    rows.append(["**Сумма по ДЦ**", b(tot["n_rps"]), b(tot["n_tls"]), b(tot["n_net"]), b(tot["n_conn"]), b(tot["l7"]), b(tot["l7_x2"])])
    print(table(["ДЦ", "`N_rps`", "`N_tls`", "`N_net`", "`N_conn`", "`N+1`", "`N*2`"], rows, ["--"] + ["----:"] * 6))

    print("\n<!-- 11.3 поды по ДЦ -->")
    rows = [[f"`{d}`", r["auth"], r["cp"], r["ws"], r["chat"], r["pgb"], r["app_cpu"], r["app_nodes"]] for d, r in p.items()]
    rows.append(["**Итого**", b(tot["auth"]), b(tot["cp"]), b(tot["ws"]), b(tot["chat"]), b(tot["pgb"]), b(tot["app_cpu"]), b(tot["app_nodes"])])
    print(table(["ДЦ", "Auth", "Control Plane", "WebSocket", "Chat", "PgBouncer", "CPU подов", "Узлы app pool"], rows,
                ["--"] + ["--:"] * 7))

    print("\n<!-- 11.3 серверы по ДЦ -->")
    rows = []
    for d, r in p.items():
        rows.append([f"`{d}`", fmt(r["sfu"]), fmt(r["rec"]), r["l7"], r["app_nodes"], r["redis_nodes"], r["auth_pg"],
                     r["citus"], r["scylla_meet"], r["scylla_chat"], r["obs"], b(fmt(servers_dc(r)))])
    rows.append(["**Итого**", b(fmt(tot["sfu"])), b(fmt(tot["rec"])), b(tot["l7"]), b(tot["app_nodes"]), b(tot["redis_nodes"]),
                 b(tot["auth_pg"]), b(tot["citus"]), b(tot["scylla_meet"]), b(tot["scylla_chat"]), b(tot["obs"]),
                 b(fmt(sum(servers_dc(r) for r in p.values())))])
    print(table(["ДЦ", "SFU", "Запись", "L7", "App", "Redis", "auth_pg", "Citus", "Scylla meeting", "Scylla chat", "Набл.", "Всего"],
                rows, ["--"] + ["--:"] * 11))

    print("\n<!-- 11.3 Scylla объём -->")
    rows = [[f"`{d}`", f"{r['scylla_meet_tb']:.2f} TB", r["scylla_meet"], f"{r['scylla_chat_tb']:.2f} TB", r["scylla_chat"]] for d, r in p.items()]
    rows.append(["**Итого**", b(f"{tot['scylla_meet_tb']:.2f} TB"), b(tot["scylla_meet"]), b(f"{tot['scylla_chat_tb']:.2f} TB"), b(tot["scylla_chat"])])
    print(table(["ДЦ", "meeting_scylla, с RF", "Узлов", "chat_scylla, с RF", "Узлов"], rows, ["--", "--:", "--:", "--:", "--:"]))

    print("\n<!-- 11.4 стоимость -->")
    total = 0
    for name, n, price in cost_lines(tot):
        total += n * price
        print(f"{name} | {fmt(n)} | {price:,.2f} | {n*price:,.2f}".replace(",", " "))
    print(f"ИТОГО {total:,.2f} ₽/мес ≈ ${total/USD:,.2f}".replace(",", " "))
    old_sfu = sum(ceil(SFU_PEAK * s / 10) + 1 for s in sh.values())
    old_rec = sum(ceil(REC_STREAM_PEAK * s / 10) + 1 for s in sh.values())
    what_if = sum(n * pr for _, n, pr in cost_lines(tot, old_sfu, old_rec))
    print(f"what-if (K=1.5, SFU 10 Gbps/узел без проверки CPU): SFU={old_sfu} rec={old_rec} total={what_if:,.2f}".replace(",", " "))
    for name, n, price in cost_lines(tot):
        print(f"  share {name}: {n*price/total*100:.2f}%")

    print("\n<!-- контрольные значения -->")
    print(f"OTHER={OTHER:.2f} INTL={INTL:.2f} EMEA_TOTAL={EMEA_TOTAL:.3f} APAC_TOTAL={APAC_TOTAL:.3f} "
          f"EMEA_REST={EMEA_REST:.3f} APAC_REST={APAC_REST:.3f}")
    print("shares:", {d: round(v, 3) for d, v in DC.items()})
    print(f"US-East part={US*(100-US_WEST_POP)/100:.3f} US-West={US*US_WEST_POP/100:.3f}")
    print(f"ARPU ratio Americas/intl = {(REV_AMER/(US+CA+LATAM))/((REV_APAC+REV_EMEA)/INTL):.2f}")
    print(f"L7: REST={fmt(REST_RPS)} WS_IN={fmt(WS_IN)} WS_OUT={fmt(WS_OUT)} RPS={fmt(L7_RPS)} NEW_TLS={fmt(L7_NEW_TLS)} "
          f"GBPS={L7_GBPS:.2f} conn/node={fmt(CONN_PER_L7)} node_price={L7_NODE_PRICE:.2f}")
    print(f"SFU: core={CORE_GBPS:.4f} Gbps node={SFU_NODE_GBPS:.3f} Gbps  SFU_PEAK={fmt(SFU_PEAK,2)}  "
          f"REC_STREAM_PEAK={fmt(REC_STREAM_PEAK,1)}")
    print(f"pods: AUTH_RPS={fmt(AUTH_RPS)} CP_RPS={fmt(CP_RPS)} WS_POD_CONN={fmt(WS_POD_CONN)} RUNTIME_OPS={fmt(RUNTIME_OPS)} "
          f"SESSION_OPS={fmt(SESSION_OPS)} app_ram={tot['app_ram']}")
    hq = (V_UP_HQ + V_DOWN_HQ + AUDIO + SCREEN) / (V_UP + V_DOWN + AUDIO + SCREEN)
    print(f"HQ ratio={hq:.4f}; remaining capacity without US-EAST={100-DC['DC-US-EAST']:.2f}%")
    print(f"L7 capacity total conn={fmt(sum(r['l7'] for r in p.values())*CONN_PER_L7)}")


if __name__ == "__main__":
    main()
