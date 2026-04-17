Discord‑подобные голос/видео‑звонки (WebRTC + SFU)

---
## Часть 1. Тема и целевая аудитория

**Проект:** Discord-клон для Австралии

**Тип сервиса:** Discord-клон платформа для общения в сообществах, где основная нагрузка создаётся групповыми видео-совещаниями, голосовыми каналами и скринкастом экрана, а текстовые каналы служат для координации общения.

**Функционал MVP:**

1. голосовые каналы (общение голосом при подключении к комнате);
2. групповые видео;
3. запуск скринкастов для гейм стриминга;
4. запись звонков и сохранение в облаке;
5. роли и разрешения (для модерации внутри канала: удаление из комнаты, выключение камеры/микрофона).

**Аналоги на рынке (глобальные):**

1. Discord ~ 200 млн MAU [^1] и 90 млн DAU [^5] (Отношение MAU/DAU ~ 0.45)
2. Microsoft Teams ~ 320 млн MAU [^4]


**Выбрвнный регион**
В процессе выбора локации была выбрана Австралия.

1) Пользуются интернетом в Австралии: 26.2 млн человек [^2]
2) 82% Австралицев играют в игры [^3], а 77% играют в игры в компании [^3]

**TAM**
Подсчет TAM (общий объем целевого рынка): 26.2 × 0.82 × 0.77 = 16.54 млн пользователей

**Расчет MAU DAU (для Австралии)**

Данных для Австралии по Mau и Dau нет, поэтому расчет этих метрик сделаем используя TAM и документ [^6].

Из него получаем коэффициен проникновения сервиса (kServiseUse) ~ 7.4%:
- Discord использовали 10% мужчин и 5% женщин среди австралийских взрослых [^6];
- Распределение по полу: 49 % мужчины и 50 % женщины [^6]

$k_{serviceUse}=0.49\cdot10\%+0.5\cdot5\%\approx7.4\%$


Также данные: 
- 84% взрослых использовали "messaging/calling apps" [^6];
- 61% использовали "app voice calls" [^6];
- среди аудитории 18–24 Discord использовали 39% респондентов[^6];

**Расчет:**
| Параметр | Формула | Значение |
|---|---|---:|
| TAM | — | 16,540,000 |
| Коэффициент использования сервиса | $k_{serviceUse}=0.49\cdot10\%+0.5\cdot5\%\approx7.4\%$ | 7.4% |
| Месячная активная аудитория (MAU) | $MAU=TAM\cdot k_{serviceUse}=16{,}540{,}000\cdot7.4\%=1{,}223{,}960$ | 1,223,960 |
| Дневная активная аудитория (DAU) | $DAU=MAU\cdot0.45=1{,}223{,}960\cdot0.45=550{,}782$ | 550,782 |


## Часть 2. Расчёт нагрузки

### Базовые коэффициенты и входные данные

| Параметр | Формула | Значение | Источник / комментарий |
|---|---|---:|---|
| MAU | — | 1,223,960 | из части 1 |
| DAU | — | 550,782 | из части 1 |
| DAU / MAU | $k_{DAU/MAU}=90/200=0.45$ | 0.45 | прокси из Discord: 90M+ DAU [^5] и 200M+ MAU [^1] |
| Audio egress на 1 concurrent voice user | $B_{voice}=\dfrac{220\ \text{Gbit/s}}{2.6\cdot10^6}=84.6\ \text{kbit/s}$ | 84.6 kbit/s | Discord Engineering: 2.6 млн concurrent voice users и >220 Gbit/s egress [^8] |
| Video ingress на 1 participant | $B_{video,in}=\dfrac{50\ \text{MB/s}\cdot8}{150}=2.67\ \text{Mbit/s}$ | 2.67 Mbit/s | LiveKit benchmark: 150 participants, 50 MB/s ingress [^9] |
| Video egress на 1 participant | $B_{video,out}=\dfrac{93\ \text{MB/s}\cdot8}{150}=4.96\ \text{Mbit/s}$ | 4.96 Mbit/s | LiveKit benchmark: 150 participants, 93 MB/s egress [^9] |
| Доля DAU, использующая voice в день | $k_{voice}=20\%$ | 20% | см. допущение 1 |
| Доля DAU, включающая camera-video в день | $k_{camera}=4\%$ | 4% | см. допущение 1 |
| Доля DAU, включающая screenshare в день | $k_{screen}=2\%$ | 2% | см. допущение 1 |
| Средняя длительность voice в день | $T_{voice}=40\ \text{мин}$ | 40 мин | см. допущение 2 |
| Средняя длительность camera-video в день | $T_{camera}=20\ \text{мин}$ | 20 мин | см. допущение 2 |
| Средняя длительность screenshare в день | $T_{screen}=15\ \text{мин}$ | 15 мин | см. допущение 2 |
| Коэффициент пика | $k_{peak}=3$ | 3 | см. допущение 3 |

**Допущения к таблице:**
1. Для Discord-like сервиса принято, что в течение дня **20% DAU** заходят в voice, **4% DAU** включают камеру и **2% DAU** включают screenshare. Это проектная нагрузочная модель, потому что точных Australia-specific product telemetry по новому сервису нет.  
2. Средняя длительность использования принята как **40 мин для voice**, **20 мин для camera-video** и **15 мин для screenshare**. Это допущение нужно, чтобы перевести DAU в среднюю concurrency.  
3. Пиковая нагрузка принята как **3× от средней**: это типовое проектное допущение для consumer-сервиса с вечерним пиком.

---

### Продуктовые метрики

| Метрика | Формула | Значение | Источник / комментарий |
|---|---|---:|---|
| MAU | — | 1,223,960 | из части 1 |
| DAU | — | 550,782 | из части 1 |
| Daily voice users | $DU_{voice}=DAU\cdot20\%=550{,}782\cdot0.20$ | 110,156 | рассчитано из DAU и $k_{voice}$ |
| Daily camera users | $DU_{camera}=DAU\cdot4\%=550{,}782\cdot0.04$ | 22,031 | рассчитано из DAU и $k_{camera}$ |
| Daily screenshare users | $DU_{screen}=DAU\cdot2\%=550{,}782\cdot0.02$ | 11,016 | рассчитано из DAU и $k_{screen}$ |
| Входы в voice room на 1 пользователя в день | $A_{join/user}=\dfrac{DU_{voice}\cdot2}{DAU}$ | 0.40 | см. допущение 4 |
| Выходы из voice room на 1 пользователя в день | $A_{leave/user}=\dfrac{DU_{voice}\cdot2}{DAU}$ | 0.40 | см. допущение 4 |
| Mute / unmute на 1 пользователя в день | $A_{mute/user}=\dfrac{DU_{voice}\cdot4}{DAU}$ | 0.80 | см. допущение 5 |
| Camera on / off на 1 пользователя в день | $A_{camera/user}=\dfrac{DU_{camera}\cdot2}{DAU}$ | 0.08 | см. допущение 6 |
| Screenshare start / stop на 1 пользователя в день | $A_{screen/user}=\dfrac{DU_{screen}\cdot2}{DAU}$ | 0.04 | см. допущение 7 |
| Recording start / stop на 1 пользователя в день | $A_{rec/user}=\dfrac{DU_{screen}\cdot2}{DAU}$ | 0.04 | см. допущение 8 |

**Допущения к таблице:**
4. На одного активного voice-user принято **2 voice sessions/day**, то есть один join и один leave на каждую сессию.  
5. На одного активного voice-user принято **4 mute/unmute действия в день**.  
6. На одного активного camera-user принято **2 camera on/off действия в день**.  
7. На одного активного screenshare-user принято **2 actions/day**: start и stop.  
8. Для MVP с записью звонков принято, что **screenshare-сессия записывается в облако**, поэтому для recording control взята та же частота действий, что и для screenshare.

---

### Средний размер хранилища на 1 пользователя в месяц

> Здесь считается **месячный прирост хранения на 1 MAU**, а не весь исторический объём. Существенным блоком хранения для MVP является именно **cloud recording**.

| Тип данных | Формула | Штук / user / month | GB / user / month | Источник / комментарий |
|---|---|---:|---:|---|
| Recording sessions | $N_{rec/user}=\dfrac{DAU}{MAU}\cdot2\%\cdot30=0.45\cdot0.02\cdot30$ | 0.27 | — | рассчитано из DAU/MAU и daily screenshare share |
| Audio inside recordings | $S_{audio/user}=0.27\cdot\dfrac{84.6\ \text{kbit/s}\cdot15\cdot60}{8\cdot10^6}$ | 0.27 | 0.0026 | bitrate аудио взят из Discord voice proxy [^8] |
| Screen video inside recordings | $S_{video/user}=0.27\cdot\dfrac{2.67\ \text{Mbit/s}\cdot15\cdot60}{8\cdot10^3}$ | 0.27 | 0.0811 | bitrate видео взят как 720p proxy из LiveKit benchmark [^9] |
| **Итого cloud recordings** | $S_{total/user}=0.0026+0.0811$ | **0.27** | **0.0837** | **83.7 MB / user / month** |

**Допущения к таблице:**
9. Для расчёта хранения принят сценарий, что запись хранится для **каждой screenshare-сессии**.  
10. Для видеочасти записи screenshare принят тот же bitrate, что и для опубликованного **720p stream** в benchmark LiveKit, потому что отдельной метрики для screenshare в источнике нет.  
11. Профили пользователей, роли, channel metadata и moderation-логи не вынесены в storage-table, потому что для такого MVP их объём на порядки меньше медиазаписей.

---

### Размер хранения по типам данных (месячный прирост)

| Тип данных | Формула | Штук / month | TB / month | Источник / комментарий |
|---|---|---:|---:|---|
| Audio inside recordings | $N_{rec}=DU_{screen}\cdot30=11{,}016\cdot30$ | 330,469 | 3.15 | рассчитано из daily screenshare users и audio bitrate [^8] |
| Screen video inside recordings | $N_{rec}=DU_{screen}\cdot30=11{,}016\cdot30$ | 330,469 | 99.26 | рассчитано из daily screenshare users и video bitrate [^9] |
| **Итого cloud recordings** | — | **330,469** | **102.41** | сумма двух строк выше |

**Комментарий к таблице:**  
Поскольку в задании не задан retention policy, в таблице показан **месячный прирост хранилища**, а не накопленный storage за всё время работы сервиса.

---

### Concurrency-метрики

| Метрика | Формула | Значение | Источник / комментарий |
|---|---|---:|---|
| Average voice CCU | $CCU_{voice,avg}=\dfrac{DU_{voice}\cdot40}{1440}$ | 3,060 | рассчитано из $DU_{voice}$ и $T_{voice}$ |
| Peak voice CCU | $CCU_{voice,peak}=CCU_{voice,avg}\cdot3$ | 9,180 | рассчитано из $k_{peak}$ |
| Average camera CCU | $CCU_{camera,avg}=\dfrac{DU_{camera}\cdot20}{1440}$ | 306 | рассчитано из $DU_{camera}$ и $T_{camera}$ |
| Peak camera CCU | $CCU_{camera,peak}=CCU_{camera,avg}\cdot3$ | 918 | рассчитано из $k_{peak}$ |
| Average screenshare CCU | $CCU_{screen,avg}=\dfrac{DU_{screen}\cdot15}{1440}$ | 115 | рассчитано из $DU_{screen}$ и $T_{screen}$ |
| Peak screenshare CCU | $CCU_{screen,peak}=CCU_{screen,avg}\cdot3$ | 344 | рассчитано из $k_{peak}$ |

**Комментарий к таблице:**  
Эта таблица нужна как промежуточный шаг: именно через CCU считаются media traffic и требования к сети.

---

### Сетевой трафик

| Тип трафика | Формула | Суточный объём (GB/day) | Средняя скорость (Gbit/s) | Пиковая скорость (Gbit/s) | Источник / комментарий |
|---|---|---:|---:|---:|---|
| Voice egress | $V_{voice,avg}=CCU_{voice,avg}\cdot84.6\ \text{kbit/s}$ | 2,795.8 | 0.259 | 0.777 | audio proxy из Discord: 2.6M concurrent users и >220 Gbit/s [^8] |
| Camera ingress | $V_{cam,in}=CCU_{camera,avg}\cdot2.67\ \text{Mbit/s}$ | 8,823.5 | 0.817 | 2.451 | LiveKit 720p ingress proxy [^9] |
| Camera egress | $V_{cam,out}=CCU_{camera,avg}\cdot4.96\ \text{Mbit/s}$ | 16,391.3 | 1.518 | 4.553 | LiveKit 720p egress proxy [^9] |
| Screenshare ingress | $V_{scr,in}=CCU_{screen,avg}\cdot2.67\ \text{Mbit/s}$ | 3,308.8 | 0.306 | 0.919 | см. допущение 10 |
| Screenshare egress | $V_{scr,out}=CCU_{screen,avg}\cdot4.96\ \text{Mbit/s}$ | 6,146.7 | 0.569 | 1.707 | см. допущение 10 |
| **Total ingress** | $V_{in}=V_{cam,in}+V_{scr,in}$ | **12,132.4** | **1.123** | **3.370** | сумма ingress-строк |
| **Total egress** | $V_{out}=V_{voice}+V_{cam,out}+V_{scr,out}$ | **25,333.8** | **2.346** | **7.037** | сумма egress-строк |
| **Total traffic** | $V_{total}=V_{in}+V_{out}$ | **37,466.1** | **3.469** | **10.407** | суммарный media traffic |

**Комментарий к таблице:**  
В traffic-table учитывается только **существенный media-plane traffic**: voice, camera-video и screenshare. Signaling-трафик не включён, потому что по объёму он значительно меньше RTP/media потока.

---

### RPS по основным типам запросов

| Тип запроса | Формула | Действий / day | Среднее RPS | Пиковое RPS | Источник / комментарий |
|---|---|---:|---:|---:|---|
| JoinVoiceRoom | $RPS_{join}=\dfrac{DU_{voice}\cdot2}{86{,}400}$ | 220,313 | 2.55 | 7.65 | см. допущение 4 |
| LeaveVoiceRoom | $RPS_{leave}=\dfrac{DU_{voice}\cdot2}{86{,}400}$ | 220,313 | 2.55 | 7.65 | см. допущение 4 |
| MuteUnmute | $RPS_{mute}=\dfrac{DU_{voice}\cdot4}{86{,}400}$ | 440,626 | 5.10 | 15.30 | см. допущение 5 |
| ToggleCamera | $RPS_{camera}=\dfrac{DU_{camera}\cdot2}{86{,}400}$ | 44,063 | 0.51 | 1.53 | см. допущение 6 |
| StartStopScreenshare | $RPS_{screen}=\dfrac{DU_{screen}\cdot2}{86{,}400}$ | 22,031 | 0.25 | 0.76 | см. допущение 7 |
| StartStopRecording | $RPS_{rec}=\dfrac{DU_{screen}\cdot2}{86{,}400}$ | 22,031 | 0.25 | 0.76 | см. допущение 8 |
| **Total signaling** | — | **969,407** | **11.22** | **33.66** | сумма строк выше |

**Комментарий к таблице:**  
RPS считается только для основных control-plane действий MVP: join/leave room, mute/unmute, camera toggle, screenshare control и recording control.


---

## Список источников

[^1]: [Статистика по дискордку за 2025 год](https://discord.com/press-releases/social-sdk-ingame-communications)

[^2]: [Data reportal Australia за 2026 год](https://datareportal.com/reports/digital-2026-australia)

[^3]: [Сколько играют в игры в Австралии - Australia Plays 2025](https://igea.net/wp-content/uploads/2025/08/AP25-Report-28_08-WITH-LINKS.pdf)

[^4]: [Mau для Micropsoft Teams](https://learn.microsoft.com/en-us/microsoftteams/platform/overview#:~:text=320%20million%20monthly%20active%20users)

[^5]: [DAU для дискорда](https://discord.com/developers/social-sdk#:~:text=90M%2B%20daily%20active%20users)

[^6]: [Медиа опрос аудитории по коммуникациям и медиа в Австралии на декабрь 2024 года](https://www.acma.gov.au/sites/default/files/2025-07/How%20we%20communicate%20-%20Executive%20summary%20and%20key%20findings_0.pdf)

[^7]: [Q1 2025. Топ приложения для бизнеса](https://sensortower.com/blog/2025-q1-unified-top-5-business%20apps-units-au-60128cd0241bc16eb8d41c6f)

[^8]: [Discord Engineering: How Discord Handles Two and Half Million Concurrent Voice Users Using WebRTC](https://discord.com/blog/how-discord-handles-two-and-half-million-concurrent-voice-users-using-webrtc)

[^9]: [LiveKit Benchmarking](https://docs.livekit.io/home/self-hosting/benchmark/)
