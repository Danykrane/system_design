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

### Продуктовые метрики

| Метрика | Формула | Значение | Источник / комментарий |
|---|---|---:|---|
| Месячная аудитория (MAU) | — | 1,223,960 | из части 1 |
| Дневная аудитория (DAU) | — | 550,782 | из части 1 |
| Среднее число пользователей голосовых комнат в день | $DU_{voice}=DAU\cdot20\%=550{,}782\cdot0.20$ | 110,156 | см. допущение 1 |
| Среднее число пользователей с камерой в день | $DU_{camera}=DAU\cdot4\%=550{,}782\cdot0.04$ | 22,031 | см. допущение 1 |
| Среднее число пользователей со скринкастом в день | $DU_{screen}=DAU\cdot2\%=550{,}782\cdot0.02$ | 11,016 | см. допущение 1 |
| Средний размер хранения на 1 пользователя: записи звонков, шт/мес | $N_{rec/user}=\dfrac{DAU}{MAU}\cdot2\%\cdot30=0.45\cdot0.02\cdot30$ | 0.27 | см. допущение 4 |
| Средний размер хранения на 1 пользователя: аудио в записях, ГБ/мес | $S_{audio/user}=0.27\cdot\dfrac{84.6\ \text{kbit/s}\cdot15\cdot60}{8\cdot10^6}$ | 0.0026 | на основе Discord voice traffic [^8] |
| Средний размер хранения на 1 пользователя: видео скринкаста в записях, ГБ/мес | $S_{video/user}=0.27\cdot\dfrac{2.67\ \text{Mbit/s}\cdot15\cdot60}{8\cdot10^3}$ | 0.0811 | на основе LiveKit 720p benchmark [^9] |
| Средний размер хранения на 1 пользователя: всего, ГБ/мес | $S_{total/user}=0.0026+0.0811$ | 0.0837 | 83.7 MB / user / month |
| Среднее число входов в голосовую комнату на 1 пользователя в день | $A_{join/user}=\dfrac{DU_{voice}\cdot2}{DAU}$ | 0.40 | см. допущение 5 |
| Среднее число выходов из голосовой комнаты на 1 пользователя в день | $A_{leave/user}=\dfrac{DU_{voice}\cdot2}{DAU}$ | 0.40 | см. допущение 5 |
| Среднее число mute / unmute на 1 пользователя в день | $A_{mute/user}=\dfrac{DU_{voice}\cdot4}{DAU}$ | 0.80 | см. допущение 6 |
| Среднее число camera on / off на 1 пользователя в день | $A_{camera/user}=\dfrac{DU_{camera}\cdot2}{DAU}$ | 0.08 | см. допущение 7 |
| Среднее число start / stop скринкаста на 1 пользователя в день | $A_{screen/user}=\dfrac{DU_{screen}\cdot2}{DAU}$ | 0.04 | см. допущение 8 |
| Среднее число start / stop записи на 1 пользователя в день | $A_{rec/user}=\dfrac{DU_{screen}\cdot2}{DAU}$ | 0.04 | см. допущение 9 |

**Допущения к продуктовым метрикам:**
### Допущения и их обоснование

1. **Доля DAU, использующая голосовые комнаты, камеру и скринкаст**
   
   В расчёте нагрузки приняты следующие проектные коэффициенты:
   - 20% DAU используют голосовые комнаты;
   - 4% DAU включают камеру;
   - 2% DAU запускают скринкаст.

   Эти значения **не являются напрямую опубликованной статистикой Discord или австралийского рынка**, поэтому используются как **проектные допущения**. Они выбраны как консервативные на фоне более широких рыночных показателей использования app-based communication в Австралии:
   - 84% взрослых использовали `messaging/calling apps`;
   - 61% использовали `app voice calls`;
   - 61% использовали `app video calls`;
   - 58% использовали communication/social app для `voice or video calls` за последние 7 дней;
   - среди аудитории 18–24 Discord использовали 39% за последние 6 месяцев, 26% за последние 7 дней и 18% — именно для `video or voice calls`.

   **Источник:** [ACMA — How we communicate, 2024](https://www.acma.gov.au/sites/default/files/2025-07/How%20we%20communicate%20-%20Executive%20summary%20and%20key%20findings_0.pdf)

2. **Средняя длительность использования**
   
   В расчёте приняты:
   - 40 минут для голосовых комнат;
   - 20 минут для camera-video;
   - 15 минут для screenshare.

   Значение **40 минут** можно использовать как внешний ориентир, потому что у бесплатных Zoom Meetings стандартный лимит встречи составляет 40 минут.  
   Значения **20 минут** и **15 минут** — это **производные консервативные допущения**, принятые как более короткие подмножества от типичной сессии.

   **Источник для 40 минут:** [Zoom Support — Understanding time limits for Zoom Meetings](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0067966)

3. **Прокси DAU / MAU**
   
   Для пересчёта MAU в DAU используется:
   $k_{DAU/MAU}=90/200=0.45$

   Это **derived proxy**, а не официальный коэффициент Discord. Он получен из двух публично заявленных метрик:
   - `90M+ daily active users` — [Discord Social SDK](https://discord.com/developers/social-sdk)
   - `200+ million monthly active users` — [Discord press release](https://discord.com/press-releases/social-sdk-ingame-communications)

4. **Запись создаётся для каждой screenshare-сессии и хранится в облаке**
   
   Это **продуктовое решение MVP**, а не внешняя статистика поведения пользователей. Оно обосновано тем, что у зрелых аналогов cloud recording является стандартным сценарием: запись запускается из meeting controls и сохраняется в облако.

   **Источник:** [Zoom Support — Starting a cloud recording](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0062627)

5. **Две голосовые сессии в день на активного пользователя**
   
   В расчёте принято **2 голосовые сессии в день** на одного активного пользователя голосовых комнат.

   Это значение является **проектным допущением**. Открытой Discord telemetry по количеству voice-room sessions/day на пользователя нет, поэтому коэффициент задаётся вручную как консервативный.

6. **Четыре действия mute / unmute в день**
   
   В расчёте принято **4 действия mute / unmute** в день на одного активного voice-user.

   Это также **проектное допущение**. Внешний источник подтверждает только наличие самого control в Discord:
   - есть отдельная команда `Toggle Mute`;
   - есть shortcut `Ctrl + Shift + M` / `⌘ + Shift + M`.

   **Источники:**  
   - [Discord Support — Discord Commands, Shortcuts, and Navigation Guide](https://support.discord.com/hc/en-us/articles/31232432266647-Discord-Commands-Shortcuts-and-Navigation-Guide)  
   - [Discord Support — How do I add different Keybinds?](https://support.discord.com/hc/en-us/articles/217083547-How-do-I-add-different-Keybinds)

7. **Два действия camera on / off в день**
   
   В расчёте принято **2 действия camera on / off** в день на одного активного пользователя с камерой.

   Это **проектное допущение**, соответствующее одной video-session в день. Внешний источник подтверждает механику включения и выключения камеры:
   - пользователь может включить камеру в звонке;
   - затем выключить её той же кнопкой.

   **Источники:**  
   - [Discord Support — Video Calls](https://support.discord.com/hc/en-us/articles/360041721052-Video-Calls)  
   - [Discord Support — Group Chat and Calls](https://support.discord.com/hc/en-us/articles/223657667-Group-Chat-and-Calls)

8. **Два действия start / stop для screenshare**
   
   В расчёте принято **2 действия в день** на одного активного пользователя со скринкастом:
   - `start screenshare`
   - `stop screenshare`

   Это не рыночная метрика, а **структурное проектное допущение**, соответствующее одной screenshare-сессии. Внешний источник подтверждает сам сценарий `Go Live / Screen Share` в Discord.

   **Источник:** [Discord Support — Go Live and Screen Share](https://support.discord.com/hc/en-us/articles/360040816151-Go-Live-and-Screen-Share)

9. **Частота управления записью совпадает с частотой screenshare**
   
   Для MVP принято, что частота действий `start / stop recording` совпадает с частотой `start / stop screenshare`.

   Это **проектное допущение**, так как запись в расчёте рассматривается как связанный со screenshare сценарий. Внешний источник подтверждает, что запись действительно управляется отдельными действиями `Record`, `Pause recording`, `Stop recording`.

   **Источник:** [Zoom Support — Starting a cloud recording](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0062627)

### Технические метрики

| Метрика | Формула | Значение | Источник / комментарий |
|---|---|---:|---|
| Размер хранения: записи звонков, шт/мес | $N_{rec}=DU_{screen}\cdot30=11{,}016\cdot30$ | 330,469 | рассчитано из daily screenshare users |
| Размер хранения: аудио в записях, ТБ/мес | $V_{audio}=330{,}469\cdot\dfrac{84.6\ \text{kbit/s}\cdot15\cdot60}{8\cdot10^{12}}$ | 3.15 | на основе Discord voice traffic [^8] |
| Размер хранения: видео скринкаста в записях, ТБ/мес | $V_{video}=330{,}469\cdot\dfrac{2.67\ \text{Mbit/s}\cdot15\cdot60}{8\cdot10^6}$ | 99.26 | на основе LiveKit 720p benchmark [^9] |
| Размер хранения: всего, ТБ/мес | $V_{total}=3.15+99.26$ | 102.41 | сумма двух строк выше |
| Сетевой трафик: голос, ГБ/сут | $V_{voice/day}=\dfrac{CCU_{voice}\cdot84.6\ \text{kbit/s}\cdot86{,}400}{8\cdot10^6}$ | 2,795.8 | $CCU_{voice}=\dfrac{DU_{voice}\cdot40}{1440}$ |
| Сетевой трафик: голос, пик, Гбит/с | $B_{voice,peak}=3\cdot\dfrac{CCU_{voice}\cdot84.6}{10^6}$ | 0.777 | на основе Discord voice traffic [^8] |
| Сетевой трафик: видео с камеры, ГБ/сут | $V_{cam/day}=\dfrac{CCU_{camera}\cdot(2.67+4.96)\cdot86{,}400}{8\cdot10^3}$ | 25,214.8 | $CCU_{camera}=\dfrac{DU_{camera}\cdot20}{1440}$ |
| Сетевой трафик: видео с камеры, пик, Гбит/с | $B_{cam,peak}=3\cdot\dfrac{CCU_{camera}\cdot(2.67+4.96)}{10^3}$ | 7.004 | на основе LiveKit 720p benchmark [^9] |
| Сетевой трафик: скринкаст, ГБ/сут | $V_{screen/day}=\dfrac{CCU_{screen}\cdot(2.67+4.96)\cdot86{,}400}{8\cdot10^3}$ | 9,454.5 | $CCU_{screen}=\dfrac{DU_{screen}\cdot15}{1440}$ |
| Сетевой трафик: скринкаст, пик, Гбит/с | $B_{screen,peak}=3\cdot\dfrac{CCU_{screen}\cdot(2.67+4.96)}{10^3}$ | 2.626 | для screenshare принят тот же 720p proxy, что и для video stream |
| Сетевой трафик: всего, ГБ/сут | $V_{traffic/day}=2{,}795.8+25{,}214.8+9{,}454.5$ | 37,465.1 | сумма трёх строк выше |
| Сетевой трафик: всего, пик, Гбит/с | $B_{traffic,peak}=0.777+7.004+2.626$ | 10.407 | сумма трёх строк выше |
| Запросы в секунду: вход в голосовую комнату, среднее RPS | $RPS_{join}=\dfrac{DU_{voice}\cdot2}{86{,}400}$ | 2.55 | см. допущение 5 |
| Запросы в секунду: вход в голосовую комнату, пиковое RPS | $RPS_{join,peak}=3\cdot2.55$ | 7.65 | см. допущение 3 |
| Запросы в секунду: выход из голосовой комнаты, среднее RPS | $RPS_{leave}=\dfrac{DU_{voice}\cdot2}{86{,}400}$ | 2.55 | см. допущение 5 |
| Запросы в секунду: выход из голосовой комнаты, пиковое RPS | $RPS_{leave,peak}=3\cdot2.55$ | 7.65 | см. допущение 3 |
| Запросы в секунду: mute / unmute, среднее RPS | $RPS_{mute}=\dfrac{DU_{voice}\cdot4}{86{,}400}$ | 5.10 | см. допущение 6 |
| Запросы в секунду: mute / unmute, пиковое RPS | $RPS_{mute,peak}=3\cdot5.10$ | 15.30 | см. допущение 3 |
| Запросы в секунду: camera on / off, среднее RPS | $RPS_{camera}=\dfrac{DU_{camera}\cdot2}{86{,}400}$ | 0.51 | см. допущение 7 |
| Запросы в секунду: camera on / off, пиковое RPS | $RPS_{camera,peak}=3\cdot0.51$ | 1.53 | см. допущение 3 |
| Запросы в секунду: start / stop скринкаста, среднее RPS | $RPS_{screen}=\dfrac{DU_{screen}\cdot2}{86{,}400}$ | 0.25 | см. допущение 8 |
| Запросы в секунду: start / stop скринкаста, пиковое RPS | $RPS_{screen,peak}=3\cdot0.25$ | 0.76 | см. допущение 3 |
| Запросы в секунду: start / stop записи, среднее RPS | $RPS_{rec}=\dfrac{DU_{screen}\cdot2}{86{,}400}$ | 0.25 | см. допущение 9 |
| Запросы в секунду: start / stop записи, пиковое RPS | $RPS_{rec,peak}=3\cdot0.25$ | 0.76 | см. допущение 3 |
| Запросы в секунду: всего, среднее RPS | — | 11.22 | сумма строк выше |
| Запросы в секунду: всего, пиковое RPS | — | 33.66 | сумма строк выше |

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
