#!/usr/bin/env python3
"""Единая модель расчёта MeetFlow.

Все числа в README (разделы 2-6, 9 и 11) получены этим скриптом, поэтому
при изменении любого допущения (например, MF_K_PEAK) достаточно поменять
константу и перезапустить:

    python3 resource/calc/meetflow_calc.py > /tmp/meetflow_tables.md

Единицы: десятичные (1 KB = 10^3 B, 1 GB = 10^9 B, 1 Gbps = 10^9 бит/с).
ВВП стран для долей ДЦ лежит рядом: imf_weo_2026apr_gdp_2025.json.
"""

import json
import math
import os

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

# Проектные допущения (раздел 2.1)
CHAT_PER_JOIN = 5            # сообщений чата на одно участие
CHAT_MSG_B = 1_000           # средний размер сообщения (лимит 4 000 символов [^6])
LIST_PER_DAU = 3             # открытий списка встреч на DAU в сутки
LOGIN_PER_DAU = 1            # созданий сессии (логинов) на DAU в сутки
CHAT_HIST_PER_JOIN = 1       # загрузок истории чата на одно участие (вход или переподключение)
REC_VIEWS_PER_REC = 1        # открытий записи на одну запись — верхняя оценка
REC_PART_B = 8_000_000       # часть multipart upload записи; S3 допускает до 10 000 частей на объект [^46]
CHAT_DEDUP_TTL_SEC = 60      # сколько хранится ключ идемпотентности сообщения
RETENTION_DAYS = 30

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
REC_PB_30D = REC_PB_DAY * RETENTION_DAYS

STORAGE = [  # (блок, название, штук, байт на штуку)
    ("Профили пользователей", "MF_USERS_STORAGE_GB", MAU, 256),
    ("Метаданные встреч, 30 дней", "MF_MEETINGS_META_STORAGE_GB", MEETINGS_DAY * RETENTION_DAYS, 256),
    ("Ссылки-приглашения, 30 дней", "MF_INVITES_STORAGE_GB", MEETINGS_DAY * RETENTION_DAYS, 128),
    ("Участники встреч, 30 дней", "MF_PARTICIPANTS_STORAGE_TB", DMP * RETENTION_DAYS, 128),
    ("Списки встреч пользователей, 30 дней", "MF_USER_MEETINGS_STORAGE_TB", DMP * RETENTION_DAYS, 128),
    ("Активные сессии", "MF_SESSIONS_STORAGE_GB", DAU, 128),
    ("Чат встречи, 30 дней", "MF_CHAT_STORAGE_TB", CHAT_DAY * RETENTION_DAYS, CHAT_MSG_B),
]
TECH_TB = sum(n * b for _, _, n, b in STORAGE) / 1e12
USERS_GB = MAU * 256 / 1e9
MEET_META_GB = MEETINGS_DAY * RETENTION_DAYS * 256 / 1e9
INVITES_GB = MEETINGS_DAY * RETENTION_DAYS * 128 / 1e9
PARTICIPANTS_TB = DMP * RETENTION_DAYS * 128 / 1e12
USER_MEETINGS_TB = DMP * RETENTION_DAYS * 128 / 1e12
SESSIONS_GB = DAU * 128 / 1e9
CHAT_TB_30D = CHAT_DAY * RETENTION_DAYS * CHAT_MSG_B / 1e12

# ---------------------------------------------------------------- 2.4 трафик и RPS
BW_AVG = {  # Гбит/с, средний
    "Video upload": AVG_ONLINE * V_UP / 1000,
    "Video download": AVG_ONLINE * V_DOWN / 1000,
    "Audio VoIP": AVG_ONLINE * AUDIO / 1000,
    "Screen sharing upper-bound": AVG_ONLINE * SCREEN / 1000,
}
MEDIA_GB_DAY = sum(BW_AVG.values()) * DAY / 8           # Гбит/с * с / 8 = ГБ/сутки
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
    "GET /meeting-chat/messages?after_seq=N": DMP * CHAT_HIST_PER_JOIN,
    "GET /users/{id}/meetings?limit=100": LIST_DAY,
    "POST /recordings/metadata": MEETINGS_DAY,
    "GET /recordings/{id}": MEETINGS_DAY * REC_VIEWS_PER_REC,
}
RPS = {k: peak(v) for k, v in EVENTS_DAY.items()}
R_LOGIN = RPS["POST /auth/login"]
R_CREATE = RPS["POST /meetings"]
R_JOIN = RPS["POST /meetings/{id}/join"]
R_LEAVE = RPS["POST /meetings/{id}/leave"]
R_HB = RPS["WS /presence/heartbeat"]
R_CHAT = RPS["POST /meeting-chat/messages"]
R_HIST = RPS["GET /meeting-chat/messages?after_seq=N"]
R_LIST = RPS["GET /users/{id}/meetings?limit=100"]
R_REC = RPS["POST /recordings/metadata"]
R_REC_VIEW = RPS["GET /recordings/{id}"]
WS_PUSH_DAY = (CHAT_DAY + DMP + DMP) * (MEET_SIZE - 1)   # доставка чата и событий join/leave

# ---------------------------------------------------------------- 3.2 ДЦ
# Доля ДЦ = доля его группы стран в мировом ВВП без материкового Китая (IMF WEO, 2025);
# США делим на восток и запад по населению (Census 2020 [^73]).
_HERE = os.path.dirname(os.path.abspath(__file__))
GDP = json.load(open(os.path.join(_HERE, "imf_weo_2026apr_gdp_2025.json"), encoding="utf-8"))["gdp_busd"]
GROUPS = {  # группа стран -> ISO-коды IMF
    "США": "USA",
    "Канада": "CAN",
    "Мексика, Центральная Америка, Карибы":
        "MEX GTM BLZ SLV HND NIC CRI PAN DOM HTI JAM TTO BHS BRB PRI ABW ATG DMA GRD KNA LCA VCT",
    "Южная Америка": "BRA ARG CHL COL PER VEN ECU BOL PRY URY GUY SUR",
    "Великобритания": "GBR",
    "Европа без Великобритании, СНГ, Ближний Восток, Африка": (
        "ALB AND ARM AUT AZE BLR BEL BIH BGR HRV CYP CZE DNK EST FIN FRA GEO DEU GRC HUN ISL IRL ITA UVK "
        "LVA LIE LTU LUX MLT MDA MNE NLD MKD NOR POL PRT ROU RUS SMR SRB SVK SVN ESP SWE CHE TUR UKR "
        "KAZ KGZ TJK TKM UZB BHR IRN IRQ ISR JOR KWT LBN OMN QAT SAU ARE YEM WBG DZA EGY LBY MAR TUN "
        "AGO BEN BWA BFA BDI CPV CMR CAF TCD COM COD COG CIV DJI GNQ SWZ ETH GAB GMB GHA GIN GNB KEN LSO "
        "LBR MDG MWI MLI MRT MUS MOZ NAM NER NGA RWA STP SEN SYC SLE SOM ZAF SSD SDN TZA TGO UGA ZMB ZWE"),
    "Индия, Пакистан, Бангладеш, Шри-Ланка и соседи": "IND PAK BGD LKA NPL BTN MDV AFG",
    "Юго-Восточная Азия, Океания, Гонконг": (
        "IDN THA VNM PHL MYS SGP MMR KHM LAO BRN TLS HKG MAC AUS NZL PNG FJI SLB VUT WSM TON KIR FSM "
        "MHL PLW NRU TUV"),
    "Япония, Корея, Тайвань, Монголия": "JPN KOR TWN MNG",
    "Материковый Китай (не обслуживаем)": "CHN",
}
GROUPS = {g: codes.split() for g, codes in GROUPS.items()}
EXCLUDED_GROUP = "Материковый Китай (не обслуживаем)"
_assigned = [c for codes in GROUPS.values() for c in codes]
assert len(_assigned) == len(set(_assigned)), "страна в двух группах"
assert set(GDP) <= set(_assigned), f"страна без группы: {set(GDP) - set(_assigned)}"
GROUP_GDP = {g: sum(GDP.get(c, 0.0) for c in codes) for g, codes in GROUPS.items()}
SERVED_GDP = sum(v for g, v in GROUP_GDP.items() if g != EXCLUDED_GROUP)
US_WEST_POP = 0.237                                  # доля населения West по Census 2020 [^73]

DC_GROUPS = {  # ДЦ -> (группа, доля группы)
    "DC-US-EAST": [("США", 1 - US_WEST_POP), ("Канада", 1), ("Мексика, Центральная Америка, Карибы", 1)],
    "DC-US-WEST": [("США", US_WEST_POP)],
    "DC-BR-SAOPAULO": [("Южная Америка", 1)],
    "DC-UK-LONDON": [("Великобритания", 1)],
    "DC-DE-FRANKFURT": [("Европа без Великобритании, СНГ, Ближний Восток, Африка", 1)],
    "DC-IN-MUMBAI": [("Индия, Пакистан, Бангладеш, Шри-Ланка и соседи", 1)],
    "DC-SG-SINGAPORE": [("Юго-Восточная Азия, Океания, Гонконг", 1)],
    "DC-JP-TOKYO": [("Япония, Корея, Тайвань, Монголия", 1)],
}
DC_RAW = {d: sum(GROUP_GDP[g] * f for g, f in parts) / SERVED_GDP * 100 for d, parts in DC_GROUPS.items()}


def round_shares(raw, nd=2):
    """Округление долей до nd знаков с сохранением суммы 100 (метод наибольшего остатка)."""
    scale = 10 ** nd
    floors = {k: math.floor(v * scale) for k, v in raw.items()}
    rest = round(100 * scale) - sum(floors.values())
    for k in sorted(raw, key=lambda k: raw[k] * scale - floors[k], reverse=True)[:rest]:
        floors[k] += 1
    return {k: v / scale for k, v in floors.items()}


DC = round_shares(DC_RAW)      # ДЦ -> доля нагрузки, %; в расчётах используются ровно эти доли
assert abs(sum(DC.values()) - 100) < 1e-9
MACRO = {
    "Америка": ["DC-US-EAST", "DC-US-WEST", "DC-BR-SAOPAULO"],
    "EMEA": ["DC-UK-LONDON", "DC-DE-FRANKFURT"],
    "APAC": ["DC-IN-MUMBAI", "DC-SG-SINGAPORE", "DC-JP-TOKYO"],
}
REV_AMER, REV_APAC, REV_EMEA = 72.1, 12.1, 15.8      # выручка Zoom FY2026 по регионам, % [^72]

# ---------------------------------------------------------------- 4. балансировка
L7_HTTPS_RPS = 341_232       # NGINX Ingress, HTTPS, ответ 1 KB, 16 CPU [^19]
L7_TLS_CPS = 6_676           # новые HTTPS-соединения (полный TLS handshake)/с, 16 CPU [^20]
L7_NET_GBPS = 8.8            # throughput NGINX Ingress, упор в 10GbE NIC стенда [^19]
L7_MSG_B = 1_000             # размер ответа в RPS-тесте [^19]
WS_CONN_B = 20_000           # NGINX держит WS-соединение (клиент+upstream) в < 20 KB [^77]
TLS_BUF_B = 34_000           # буферы TLS, если не освобождены (SSL_MODE_RELEASE_BUFFERS) [^78]
L7_CONN_B = WS_CONN_B + TLS_BUF_B
L7_NODE_RAM_GB, L7_RAM_RESERVED_GB = 64, 8

REST_RPS = (R_LOGIN + R_CREATE + R_JOIN + R_LEAVE + R_LIST + R_REC + R_REC_VIEW + R_CHAT + R_HIST)
WS_IN = R_HB
WS_OUT = (R_CHAT + R_JOIN + R_LEAVE) * (MEET_SIZE - 1)   # доставка чата и presence-событий
L7_RPS = REST_RPS + WS_IN + WS_OUT
L7_NEW_TLS = REST_RPS + R_JOIN       # худший случай: каждый REST-запрос без keep-alive + WSS connect на join
L7_GBPS = L7_RPS * L7_MSG_B * 8 / 1e9
CONN_PER_L7 = (L7_NODE_RAM_GB - L7_RAM_RESERVED_GB) * 1e9 / L7_CONN_B

IPVS_CONN_B = 128 + 8        # запись в таблице соединений IPVS + элемент хеш-таблицы [ipvs Kconfig]
IPVS_NODE_GBPS = 10          # EL11-SSD-10GE: директор видит только входящий трафик (Direct Routing)

# ---------------------------------------------------------------- 11. нормативы
JITSI_MBPS, JITSI_CPU, JITSI_CORES = 550.4, 0.203, 4   # [^74]
CORE_GBPS = JITSI_MBPS / (JITSI_CPU * JITSI_CORES) / 1000   # ≈ 0.678 Гбит/с на ядро при 100% CPU
CPU_TARGET = 0.7
SFU_CORES = 6                                         # EL11-SSD-10GE [^66]
SFU_NODE_GBPS = round(min(10.0, SFU_CORES * CORE_GBPS * CPU_TARGET), 3)   # 2.847

WS_POD_CONN = int(6e9 / WS_CONN_B)    # под 4 CPU / 8 GB, 6 GB под соединения
AUTH_POD_RPS, CP_POD_RPS, CHAT_POD_RPS = 1_000, 1_500, 5_000
NODE_CORES_USABLE = 12                # CL34-NVMe: 14 ядер, 2 под ОС/kubelet
REDIS_SHARD_OPS = 120_000             # [^79]
SCYLLA_NODE_TB = 1.0                  # CL34-NVMe 2x1 TB, <= 50% заполнения под compaction

AUTH_RPS = R_LOGIN + R_CREATE + R_JOIN
CP_RPS = R_CREATE + R_JOIN + R_LEAVE + R_LIST + R_REC + R_REC_VIEW
CHAT_RPS = R_CHAT + R_HIST
RUNTIME_OPS = R_HB + R_JOIN + R_LEAVE + R_CREATE + R_CHAT + R_CHAT   # INCR chat_seq + SET NX ключа идемпотентности
SESSION_OPS = (R_CREATE + R_JOIN + R_LIST + R_REC_VIEW) + R_LOGIN
CITUS_READS = (R_JOIN + R_LEAVE + R_REC) + R_JOIN + R_REC_VIEW   # meetings + meeting_invite_links + recordings
CITUS_GB = MEET_META_GB + INVITES_GB + MEET_META_GB            # meetings + ссылки + recordings (по 256 B)
USERS_READS = R_LOGIN + R_CREATE + R_JOIN

PRICE = {  # Selectel, цены на 11.10.2026 с НДС 22% [^66][^67][^69][^70]
    "k8s": 17_085.59, "el11": 14_000, "cl34": 13_600, "bl18": 34_900,
    "s3_gb": 0.89,
    "vcpu": 735.19, "ram_gb": 267.34, "ssd_gb": 10.48,
}
L7_NODE_PRICE = 24 * PRICE["vcpu"] + L7_NODE_RAM_GB * PRICE["ram_gb"] + 100 * PRICE["ssd_gb"]
USD = 84.90                   # курс ЦБ РФ на 10.10.2026
TRAFFIC_INCL_TB = 300         # ТБ/мес на сервер без ограничения полосы (порт > 1 Гбит/с) [^71]
TRAFFIC_STEP_TB, TRAFFIC_STEP_RUB = 3, 336   # увеличение лимита: шаг 3 ТБ (10 Мбит/с) за 336 ₽/мес [^66]

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
        r["ipvs_ram_gb"] = r["conn"] * IPVS_CONN_B / 1e9
        r["ipvs_base"] = max(1, ceil(r["l7_gbps"] / IPVS_NODE_GBPS))
        r["ipvs"] = r["ipvs_base"] + 1                 # active + standby (keepalived, VRRP)
        r["sfu_gbps"] = SFU_PEAK * s
        r["sfu"] = ceil(r["sfu_gbps"] / SFU_NODE_GBPS) + 1
        r["rec_gbps"] = REC_STREAM_PEAK * s
        r["rec"] = ceil(r["rec_gbps"] / SFU_NODE_GBPS) + 1
        r["auth"] = ceil(AUTH_RPS * s / AUTH_POD_RPS) + 1
        r["cp"] = ceil(CP_RPS * s / CP_POD_RPS) + 1
        r["ws"] = ceil(r["conn"] / WS_POD_CONN) + 1
        r["chat"] = ceil(CHAT_RPS * s / CHAT_POD_RPS) + 1
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
    return (r["sfu"] + r["rec"] + r["ipvs"] + r["l7"] + r["app_nodes"] + r["redis_nodes"] + r["auth_pg"]
            + r["citus"] + r["scylla_meet"] + r["scylla_chat"] + r["obs"])


def cost_lines(tot, sfu_n=None, rec_n=None):
    n_dc = len(DC)
    return [
        ("Kubernetes-кластер/3 зоны доступности", n_dc, PRICE["k8s"]),
        ("L4 (IPVS + keepalived)", tot["ipvs"], PRICE["el11"]),
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
    total_servers = sum(servers_dc(r) for r in p.values())

    print("<!-- 2.2 хранилище на пользователя (на MAU за 30 дней) -->")
    per_user = [
        ("Профиль", 1, 256),
        ("Созданные встречи", MEETINGS_DAY * RETENTION_DAYS / MAU, 256),
        ("Ссылки-приглашения", MEETINGS_DAY * RETENTION_DAYS / MAU, 128),
        ("Участия во встречах", DMP * RETENTION_DAYS / MAU, 128),
        ("Строки списка встреч", DMP * RETENTION_DAYS / MAU, 128),
        ("Сообщения чата", CHAT_DAY * RETENTION_DAYS / MAU, CHAT_MSG_B),
        ("Записи встреч, worst-case", MEETINGS_DAY * RETENTION_DAYS / MAU, REC_SIZE_GB * 1e9),
    ]
    for name, n, bb in per_user:
        print(f"{name}: {n:.2f} шт × {bb:,.0f} B = {n*bb:,.0f} B".replace(",", " "))
    print(f"итого без записей: {sum(n*bb for nm, n, bb in per_user if 'Запис' not in nm)/1e3:.1f} KB")

    print("\n<!-- 2.2 действий на DAU в сутки -->")
    for k_, v in EVENTS_DAY.items():
        print(f"{k_}: {v/DAU:.2f}")
    print(f"WS push (доставка другим участникам): {WS_PUSH_DAY/DAU:.1f}")

    print("\n<!-- 2.3 хранение: штук и объём -->")
    for blk, nm, n, bb in STORAGE:
        print(f"{blk} | {nm} | {fmt(n)} шт | {n*bb/1e9:,.2f} GB".replace(",", " "))
    print(f"TECH_TB={TECH_TB:.3f}  REC_SIZE_GB={REC_SIZE_GB:.4f}  REC_PB_DAY={REC_PB_DAY:.3f}  REC_PB_30D={REC_PB_30D:.2f}  "
          f"TOTAL_30D_PB={REC_PB_30D + TECH_TB/1000:.3f}")

    print("\n<!-- 2.4 RPS -->")
    names = {
        "POST /auth/login": "MF_LOGIN_RPS", "POST /meetings": "MF_CREATE_MEETING_RPS",
        "POST /meetings/{id}/join": "MF_JOIN_RPS", "POST /meetings/{id}/leave": "MF_LEAVE_RPS",
        "WS /presence/heartbeat": "MF_HEARTBEAT_RPS", "POST /meeting-chat/messages": "MF_CHAT_RPS",
        "GET /meeting-chat/messages?after_seq=N": "MF_CHAT_HISTORY_RPS",
        "GET /users/{id}/meetings?limit=100": "MF_LIST_RPS", "POST /recordings/metadata": "MF_RECORDING_META_RPS",
        "GET /recordings/{id}": "MF_RECORDING_VIEW_RPS",
    }
    for k_, v in EVENTS_DAY.items():
        print(f"| `{k_}` | `{names[k_]}` | {fmt(v)} | **{fmt(v/DAY)}** | **{fmt(RPS[k_])}** |")
    print(f"| WS push | `MF_WS_PUSH_RPS` | {fmt(WS_PUSH_DAY)} | **{fmt(WS_PUSH_DAY/DAY)}** | **{fmt(WS_PUSH_DAY/DAY*K)}** |")
    print(f"MEDIA_GB_DAY={fmt(MEDIA_GB_DAY)}  MEDIA_PEAK={fmt(MEDIA_PEAK, 2)}  REC_STREAM_PEAK={fmt(REC_STREAM_PEAK, 1)}")

    print("\n<!-- 3.2 группы стран по ВВП -->")
    rows = []
    for g, v in GROUP_GDP.items():
        share = "—" if g == EXCLUDED_GROUP else f"{v / SERVED_GDP * 100:.2f}%"
        rows.append([g, fmt(v, 1), share])
    rows.append(["**Итого без Китая**", b(fmt(SERVED_GDP, 1)), "**100%**"])
    print(table(["Группа стран", "ВВП 2025, млрд $", "Доля"], rows, ["---", "---:", "---:"]))
    print(f"\nWEO world (сумма стран) = {sum(GDP.values()):.1f}")
    print("DC raw:", {d: round(v, 4) for d, v in DC_RAW.items()})
    print("DC rounded:", DC)
    for m, ds in MACRO.items():
        print(f"  {m}: {sum(DC[d] for d in ds):.2f}%")
    us_east_us = GROUP_GDP["США"] * (1 - US_WEST_POP) / SERVED_GDP * 100
    us_west_us = GROUP_GDP["США"] * US_WEST_POP / SERVED_GDP * 100
    print(f"  US east part={us_east_us:.2f}  US west part={us_west_us:.2f}  US total={GROUP_GDP['США']/SERVED_GDP*100:.2f}")
    print("  Zoom revenue: Americas 72.1, EMEA 15.8, APAC 12.1")

    print("\n<!-- 3.3 продуктовая нагрузка -->")
    rows = [[f"`{d}`", f"{r['share']:.2f}%", b(fmt(DAU*sh[d])), b(fmt(DMP*sh[d])), b(fmt(MEETINGS_DAY*sh[d])),
             b(fmt(PEAK_ONLINE*sh[d]))] for d, r in p.items()]
    rows.append(["**Итого**", "**100%**", b(fmt(DAU)), b(fmt(DMP)), b(fmt(MEETINGS_DAY)), b(fmt(PEAK_ONLINE))])
    print(table(["ДЦ", "Доля", "DAU", "Участий/сутки", "Встреч/сутки", "Peak online = WSS-соединений"], rows,
                ["--", "---:", "--:", "------------:", "-----------:", "----------:"]))

    print("\n<!-- 3.3 пиковый RPS -->")
    keys = list(EVENTS_DAY)
    short = ["`login`", "`create`", "`join`", "`leave`", "`heartbeat`", "`chat`", "`chat history`", "`list`",
             "`recording meta`", "`recording view`"]
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

    print("\n<!-- 4.5 L7 формулы -->")
    print(f"REST={fmt(REST_RPS)} WS_IN={fmt(WS_IN)} WS_OUT={fmt(WS_OUT)} L7_RPS={fmt(L7_RPS)} NEW_TLS={fmt(L7_NEW_TLS)} "
          f"GBPS={L7_GBPS:.2f} CONN={fmt(PEAK_ONLINE)} conn/node={fmt(CONN_PER_L7)} ({CONN_PER_L7/1e6:.3f} млн)")

    print("\n<!-- 4.5 L7 нагрузка -->")
    rows = [[f"`{d}`", b(fmt(r["l7_rps"])), fmt(r["l7_tls"]), f"{r['l7_gbps']:.2f}", b(fmt(r["conn"]))] for d, r in p.items()]
    rows.append(["**Сумма по ДЦ**", b(fmt(tot["l7_rps"])), b(fmt(tot["l7_tls"])), b(f"{tot['l7_gbps']:.2f}"), b(fmt(tot["conn"]))])
    print(table(["ДЦ", "L7 peak RPS", "Новых TLS/с", "L7 Gbps", "WSS-соединений"], rows, ["--", "----------:", "----------:", "------:", "-------------:"]))
    print()
    rows = [[f"`{d}`", r["n_rps"], r["n_tls"], r["n_net"], r["n_conn"], b(r["l7"]), r["l7_x2"]] for d, r in p.items()]
    rows.append(["**Сумма по ДЦ**", b(tot["n_rps"]), b(tot["n_tls"]), b(tot["n_net"]), b(tot["n_conn"]), b(tot["l7"]), b(tot["l7_x2"])])
    print(table(["ДЦ", "`N_rps`", "`N_tls`", "`N_net`", "`N_conn`", "`N+1`", "`N*2`"], rows, ["--"] + ["----:"] * 6))

    print("\n<!-- 4.6 L4 IPVS -->")
    rows = [[f"`{d}`", fmt(r["conn"]), f"{r['ipvs_ram_gb']:.2f} GB", f"{r['l7_gbps']:.2f}", r["ipvs_base"], b(r["ipvs"])]
            for d, r in p.items()]
    rows.append(["**Сумма по ДЦ**", b(fmt(tot["conn"])), b(f"{tot['ipvs_ram_gb']:.2f} GB"), b(f"{tot['l7_gbps']:.2f}"),
                 b(tot["ipvs_base"]), b(tot["ipvs"])])
    print(table(["ДЦ", "Соединений в таблице IPVS", "Память под таблицу", "Входящий трафик, Gbps (не больше)", "`N`", "`N+1`"],
                rows, ["--", "--:", "--:", "--:", "--:", "--:"]))

    print("\n<!-- 5.2 / 6 ключевые нагрузки -->")
    print(f"users reads={fmt(USERS_READS)} writes<= {fmt(R_LOGIN)}")
    print(f"sessions reads={fmt(R_CREATE + R_JOIN + R_LIST + R_REC_VIEW)} writes={fmt(R_LOGIN)} SESSION_OPS={fmt(SESSION_OPS)}")
    print(f"meetings reads={fmt(R_JOIN + R_LEAVE + R_REC)} writes={fmt(R_CREATE)}")
    print(f"participants reads={fmt(R_JOIN)} writes={fmt(R_JOIN + R_LEAVE)}")
    print(f"invites reads={fmt(R_JOIN)} writes={fmt(R_CREATE)}")
    print(f"user_meetings reads={fmt(R_LIST)} x100 writes={fmt(R_CREATE + R_JOIN + R_LEAVE)}")
    print(f"chat reads<= {fmt(R_HIST)} x100 writes={fmt(R_CHAT)}")
    print(f"recordings reads<= {fmt(R_REC_VIEW)} writes={fmt(R_REC)}")
    parts_peak = REC_STREAM_PEAK * 1e9 / 8 / REC_PART_B
    inflight_gb_peak = PEAK_MEETINGS_ONLINE * REC_SIZE_GB / 2
    inflight_parts_peak = inflight_gb_peak * 1e9 / REC_PART_B
    print(f"upload_buffer: PUT/s peak={fmt(parts_peak)} avg={fmt(parts_peak / K)}; in-flight peak={inflight_gb_peak/1e3:.1f} TB, "
          f"parts={fmt(inflight_parts_peak)}; parts per recording={REC_SIZE_GB*1e9/REC_PART_B:.1f}")
    print(f"CITUS_READS={fmt(CITUS_READS)} CITUS_GB={CITUS_GB:.1f}")
    big = max(DC, key=DC.get)
    print(f"largest DC {big}: meetings rows={fmt(MEETINGS_DAY*RETENTION_DAYS*sh[big])} citus GB={CITUS_GB*sh[big]:.1f} "
          f"citus reads={fmt(CITUS_READS*sh[big])}")

    print("\n<!-- 6.6 нагрузка на строки -->")
    lines = [
        ("POST /auth/login", R_LOGIN, 2), ("POST /meetings", R_CREATE, 4), ("POST /meetings/{id}/join", R_JOIN, 6),
        ("POST /meetings/{id}/leave", R_LEAVE, 3), ("WS /presence/heartbeat", R_HB, 1),
        ("POST /meeting-chat/messages", R_CHAT, 3), ("GET /meeting-chat/messages?after_seq=N", R_HIST, 100),
        ("GET /users/{id}/meetings?limit=100", R_LIST, 100), ("POST /recordings/metadata", R_REC, 2),
        ("GET /recordings/{id}", R_REC_VIEW, 2),
    ]
    for nm, r_, n in lines:
        print(f"{nm}: {fmt(r_)} x {n} = {fmt(r_*n)}")

    print("\n<!-- 6.8 кеш -->")
    print(f"meetings_runtime: {PEAK_MEETINGS_ONLINE*512/1e9:.3f} GB, ops={fmt(RUNTIME_OPS)}")
    print(f"user_sessions: {SESSIONS_GB:.2f} GB, ops={fmt(SESSION_OPS)}")
    print(f"active_invite_tokens: {MEETINGS_DAY*128/1e9:.2f} GB, ops={fmt(R_JOIN)}")
    print(f"user_meetings_top100: {DAU*100*128/1e12:.3f} TB, rows/s={fmt(R_LIST*100)}")
    print(f"chat_last100: {PEAK_MEETINGS_ONLINE*100*CHAT_MSG_B/1e9:.2f} GB, rows/s<= {fmt(R_HIST*100)}")
    print(f"chat_dedup: {R_CHAT*CHAT_DEDUP_TTL_SEC*100/1e9:.2f} GB (100 B x TTL {CHAT_DEDUP_TTL_SEC}s), ops={fmt(R_CHAT)}")
    print(f"sessions per DC max: raw {SESSIONS_GB*sh[big]:.2f} GB, with replica {SESSIONS_GB*sh[big]*2:.2f} GB")

    print("\n<!-- 9.2 отказ ДЦ -->")
    rec_pp = (V_DOWN + AUDIO) / MEET_SIZE
    full = V_UP + V_DOWN + AUDIO + SCREEN
    hq = V_UP_HQ + V_DOWN_HQ + AUDIO + SCREEN
    print(f"full={full:.2f} hq={hq:.2f} ratio={hq/full*100:.2f}%; with rec: {(hq+rec_pp)/(full+rec_pp)*100:.2f}% "
          f"(rec per participant {rec_pp:.3f})")
    for d in [big, AUTH_PRIMARY_DC]:
        rest = 100 - DC[d]
        l7_left = sum(r["l7"] for dd, r in p.items() if dd != d)
        print(f"fail {d} ({DC[d]:.2f}%): remaining={rest:.2f}%  L7 nodes left={l7_left} -> "
              f"{l7_left*CONN_PER_L7/1e6:.1f} млн соединений vs peak {PEAK_ONLINE/1e6:.2f} млн")
    print("receivers for", big, ": UK, IN by order; capacity UK+IN =", DC["DC-UK-LONDON"] + DC["DC-IN-MUMBAI"])

    print("\n<!-- 11.2 сводные -->")
    print(f"core={CORE_GBPS:.4f} Gbps; at {CPU_TARGET:.0%}: {CORE_GBPS*CPU_TARGET:.4f}; node={SFU_NODE_GBPS} Gbps; "
          f"SFU_PEAK={fmt(SFU_PEAK, 2)}; REC_STREAM_PEAK={fmt(REC_STREAM_PEAK, 1)}")
    print(f"AUTH_RPS={fmt(AUTH_RPS)} CP_RPS={fmt(CP_RPS)} CHAT_RPS={fmt(CHAT_RPS)} WS_POD_CONN={fmt(WS_POD_CONN)} "
          f"hb per pod={fmt(R_HB / PEAK_ONLINE * WS_POD_CONN)} RUNTIME_OPS={fmt(RUNTIME_OPS)} SESSION_OPS={fmt(SESSION_OPS)}")
    print(f"pods total: auth={tot['auth']} cp={tot['cp']} ws={tot['ws']} chat={tot['chat']} pgb={tot['pgb']} "
          f"cpu={tot['app_cpu']} ram={tot['app_ram']} nodes={tot['app_nodes']}")

    print("\n<!-- 11.3 поды по ДЦ -->")
    rows = [[f"`{d}`", r["auth"], r["cp"], r["ws"], r["chat"], r["pgb"], r["app_cpu"], r["app_nodes"]] for d, r in p.items()]
    rows.append(["**Итого**", b(tot["auth"]), b(tot["cp"]), b(tot["ws"]), b(tot["chat"]), b(tot["pgb"]), b(tot["app_cpu"]), b(tot["app_nodes"])])
    print(table(["ДЦ", "Auth", "Control Plane", "WebSocket", "Chat", "PgBouncer", "CPU подов", "Узлы app pool"], rows,
                ["--"] + ["--:"] * 7))

    print("\n<!-- 11.3 серверы по ДЦ -->")
    rows = []
    for d, r in p.items():
        rows.append([f"`{d}`", fmt(r["sfu"]), fmt(r["rec"]), r["ipvs"], r["l7"], r["app_nodes"], r["redis_nodes"], r["auth_pg"],
                     r["citus"], r["scylla_meet"], r["scylla_chat"], r["obs"], b(fmt(servers_dc(r)))])
    rows.append(["**Итого**", b(fmt(tot["sfu"])), b(fmt(tot["rec"])), b(tot["ipvs"]), b(tot["l7"]), b(tot["app_nodes"]),
                 b(tot["redis_nodes"]), b(tot["auth_pg"]), b(tot["citus"]), b(tot["scylla_meet"]), b(tot["scylla_chat"]),
                 b(tot["obs"]), b(fmt(total_servers))])
    print(table(["ДЦ", "SFU", "Запись", "L4", "L7", "App", "Redis", "auth_pg", "Citus", "Scylla meeting", "Scylla chat",
                 "Набл.", "Всего"], rows, ["--"] + ["--:"] * 12))

    print("\n<!-- 11.3 Scylla объём -->")
    rows = [[f"`{d}`", f"{r['scylla_meet_tb']:.2f} TB", r["scylla_meet"], f"{r['scylla_chat_tb']:.2f} TB", r["scylla_chat"]] for d, r in p.items()]
    rows.append(["**Итого**", b(f"{tot['scylla_meet_tb']:.2f} TB"), b(tot["scylla_meet"]), b(f"{tot['scylla_chat_tb']:.2f} TB"), b(tot["scylla_chat"])])
    print(table(["ДЦ", "meeting_scylla, с RF", "Узлов", "chat_scylla, с RF", "Узлов"], rows, ["--", "--:", "--:", "--:", "--:"]))

    print("\n<!-- 11.3 сводка по конфигурациям: CPU / RAM -->")
    cfg = [("L4 (IPVS)", tot["ipvs"], 6, 32), ("Ingress L7", tot["l7"], 24, 64), ("app pool", tot["app_nodes"], 14, 64),
           ("SFU", tot["sfu"], 6, 32), ("rec", tot["rec"], 6, 32), ("Redis", tot["redis_nodes"], 14, 64),
           ("auth_pg", tot["auth_pg"], 16, 128), ("Citus", tot["citus"], 16, 128), ("Scylla meet", tot["scylla_meet"], 14, 64),
           ("Scylla chat", tot["scylla_chat"], 14, 64), ("obs", tot["obs"], 14, 64)]
    for nm, n, c, ram in cfg:
        print(f"{nm}: {fmt(n)} x {c} CPU = {fmt(n*c)} CPU; RAM {fmt(n*ram)} GB")
    print(f"L7 Gbps per node = {L7_GBPS / tot['l7']:.2f}")

    print("\n<!-- 11.4 стоимость -->")
    total = 0
    for name, n, price in cost_lines(tot):
        total += n * price
        print(f"{name} | {fmt(n)} | {price:,.2f} | {n*price:,.2f}".replace(",", " "))
    print(f"L7_NODE_PRICE = {L7_NODE_PRICE:.2f}")
    print(f"ИТОГО {total:,.2f} ₽/мес ≈ ${total/USD:,.2f}".replace(",", " "))
    for name, n, price in cost_lines(tot):
        print(f"  share {name}: {n*price/total*100:.2f}%  ({n*price/1e6:.2f} млн)")
    s3 = REC_PB_30D * 1e6 * PRICE["s3_gb"]
    sfu = tot["sfu"] * PRICE["el11"]
    rec = tot["rec"] * PRICE["el11"]
    print(f"  structure: S3 {s3/1e6:.2f} ({s3/total*100:.1f}%), SFU {sfu/1e6:.2f} ({sfu/total*100:.1f}%), "
          f"rec {rec/1e6:.2f} ({rec/total*100:.1f}%), other {(total-s3-sfu-rec)/1e6:.2f} ({(total-s3-sfu-rec)/total*100:.1f}%)")
    old_sfu = sum(ceil(SFU_PEAK * s / 10) + 1 for s in sh.values())
    old_rec = sum(ceil(REC_STREAM_PEAK * s / 10) + 1 for s in sh.values())
    what_if = sum(n * pr for _, n, pr in cost_lines(tot, old_sfu, old_rec))
    print(f"what-if SFU 10 Gbps/узел без проверки CPU: SFU={fmt(old_sfu)} rec={fmt(old_rec)} total={what_if/1e6:,.2f} млн "
          f"(разница {(total-what_if)/1e6:,.2f} млн)".replace(",", " "))

    print("\n<!-- 11.4 внешний трафик SFU (оценка по публичному тарифу) -->")
    media_tb_month = MEDIA_GB_DAY * 30 / 1000
    incl_tb = TRAFFIC_INCL_TB * tot["sfu"]
    extra_tb = max(0.0, media_tb_month - incl_tb)
    steps = ceil(extra_tb / TRAFFIC_STEP_TB)
    traffic_rub = steps * TRAFFIC_STEP_RUB
    print(f"media per month = {fmt(media_tb_month)} TB ({media_tb_month/1e6:.2f} EB); per SFU node = {media_tb_month/tot['sfu']:.0f} TB")
    print(f"included = {fmt(incl_tb)} TB; extra = {fmt(extra_tb)} TB; steps = {fmt(steps)}; cost = {traffic_rub/1e6:,.2f} млн ₽/мес")
    print(f"ИТОГО с трафиком {(total + traffic_rub)/1e6:,.2f} млн ₽/мес ≈ ${(total + traffic_rub)/USD/1e6:,.2f} млн")
    print(f"servers total = {fmt(total_servers)}")


if __name__ == "__main__":
    main()
