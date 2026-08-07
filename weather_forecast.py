#!/usr/bin/env python3
"""
每日天气预报脚本
数据源：中国天气网 (weather.com.cn) 官方 API
城市通过环境变量 WEATHER_CITY_CODE 配置，昨日对比由本地缓存自记录。
"""
import json
import os
import re
import sys
import urllib.request
import urllib.parse
from datetime import date, timedelta, datetime

# ====== 配置（环境变量） ======
CITY_CODE = os.environ.get("WEATHER_CITY_CODE", "").strip()
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
if not CHAT_ID and len(sys.argv) > 1:
    CHAT_ID = sys.argv[1]

# ====== 昨日天气记录（本地缓存，无需外部API） ======
YESTERDAY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".weather_yesterday.json")

def load_yesterday():
    """读取本地记录的昨天天气数据，返回 (max, min) 或 None"""
    try:
        if os.path.exists(YESTERDAY_FILE):
            with open(YESTERDAY_FILE, "r") as f:
                data = json.load(f)
            yesterday_str = (date.today() - timedelta(days=1)).isoformat()
            if data.get("date") == yesterday_str:
                return (data["max"], data["min"])
    except Exception:
        pass
    return None

def save_today(today_max, today_min):
    """记录今天的天气到本地文件"""
    try:
        with open(YESTERDAY_FILE, "w") as f:
            json.dump({
                "date": date.today().isoformat(),
                "max": today_max,
                "min": today_min,
            }, f)
    except Exception:
        pass

# ====== 农历 ======
lunar_month_names = ["", "正月", "二月", "三月", "四月", "五月", "六月",
                     "七月", "八月", "九月", "十月", "冬月", "腊月"]
lunar_day_names = ["", "初一","初二","初三","初四","初五","初六","初七","初八","初九","初十",
                   "十一","十二","十三","十四","十五","十六","十七","十八","十九","二十",
                   "廿一","廿二","廿三","廿四","廿五","廿六","廿七","廿八","廿九","三十"]
weekday_map = {0:"星期一",1:"星期二",2:"星期三",3:"星期四",4:"星期五",5:"星期六",6:"星期日"}

# ====== 天气图标 ======
def get_icon(weather):
    if "雷" in weather: return "⛈"
    if "雨" in weather:
        if "暴" in weather: return "🌊"
        if "大" in weather: return "🌧"
        return "🌦"
    if "晴" in weather: return "☀️"
    if "云" in weather: return "⛅"
    if "阴" in weather: return "☁️"
    if "雾" in weather: return "🌫"
    if "雪" in weather: return "❄️"
    return "🌤"

# ====== 表格宽度计算 ======
def is_emoji(ch):
    cp = ord(ch)
    if 0x1F000 <= cp <= 0x1FAFF: return True
    if 0x2600 <= cp <= 0x27BF: return True
    if 0x2B00 <= cp <= 0x2BFF: return True
    return False

def disp_width(s):
    w = 0
    for ch in s:
        cp = ord(ch)
        if cp == 0xFE0F: continue
        if is_emoji(ch) or (0x4E00 <= cp <= 0x9FFF) or (0x3000 <= cp <= 0x303F) or (0x20000 <= cp <= 0x2FFFF) or (0xFF01 <= cp <= 0xFF60):
            w += 2
        else:
            w += 1
    return w

def pad_center(s, width):
    d = width - disp_width(s)
    if d <= 0: return s
    left = d // 2
    right = d - left
    return " " * left + s + " " * right

# ====== 天气 API ======
def fetch_page(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "http://www.weather.com.cn/",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def extract_balanced_json(html, start_idx):
    brace_start = html.find("{", start_idx)
    if brace_start < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(brace_start, len(html)):
        ch = html[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return html[brace_start:i+1]
    return None

def fetch_weather():
    """获取指定城市天气数据（7天预报 + 实时观测 + 风力信息）"""
    url = f"http://www.weather.com.cn/weather/{CITY_CODE}.shtml"
    html = fetch_page(url)

    # 从 HTML 提取每日摘要（天气、最高/最低温）
    day_items = re.findall(
        r'<h1>(.*?)</h1>.*?class="wea"[^>]*>([^<]+)</p>.*?<span>(\d+)</span>.*?<i>(\d+).*?</i>',
        html, re.DOTALL
    )

    forecast = []
    for date_label, weather, high, low in day_items:
        weather = re.sub(r'<[^>]+>', '', weather).strip()
        forecast.append({
            "date": date_label.strip(),
            "weather": weather,
            "high": int(high),
            "low": int(low),
            "wind": "",
        })

    # 从 hour3data 提取风力信息
    for marker in ["hour3data =", "hour3data="]:
        idx = html.find(marker)
        if idx >= 0:
            offset = len(marker)
            raw = extract_balanced_json(html, idx + offset)
            if raw:
                try:
                    h3d = json.loads(raw)
                    for i in range(1, min(7, len(h3d.get("7d", [])))):
                        day_data = h3d["7d"][i]
                        for h in day_data[:3]:
                            parts = h.split(",")
                            if len(parts) >= 6 and parts[4] and parts[5]:
                                forecast[i]["wind"] = f"{parts[4]} {parts[5]}"
                                break
                except:
                    pass
            break

    # 实时观测
    for marker in ["observe24h_data =", "observe24h_data="]:
        idx = html.find(marker)
        if idx >= 0:
            break
    else:
        idx = -1

    observe = {}
    if idx >= 0:
        offset = len(marker)
        raw = extract_balanced_json(html, idx + offset)
        if raw:
            try:
                od = json.loads(raw)["od"]
                obs_list = od.get("od2", [])
                if obs_list:
                    latest = obs_list[0]
                    observe = {
                        "temp": latest.get("od22", ""),
                        "wind_dir": latest.get("od24", ""),
                        "wind_level": latest.get("od25", ""),
                        "humidity": latest.get("od27", ""),
                    }
            except:
                pass

    return forecast, observe

# ====== 节气 & 节日 ======
solar_terms = [
    (1,5,"小寒"), (1,20,"大寒"), (2,3,"立春"), (2,18,"雨水"),
    (3,5,"惊蛰"), (3,20,"春分"), (4,4,"清明"), (4,20,"谷雨"),
    (5,5,"立夏"), (5,21,"小满"), (6,5,"芒种"), (6,21,"夏至"),
    (7,6,"小暑"), (7,22,"大暑"), (8,7,"立秋"), (8,23,"处暑"),
    (9,7,"白露"), (9,23,"秋分"), (10,8,"寒露"), (10,23,"霜降"),
    (11,7,"立冬"), (11,22,"小雪"), (12,6,"大雪"), (12,21,"冬至"),
]
festivals = [(1,1,"元旦"), (2,14,"情人节"), (3,8,"妇女节"), (5,1,"劳动节"), (6,1,"儿童节"),
             (7,1,"建党节"), (8,1,"建军节"), (9,10,"教师节"), (10,1,"国庆节"), (12,25,"圣诞节")]

def get_upcoming(today, days=14):
    result = []
    for d_offset in range(1, days + 1):
        d = today + timedelta(days=d_offset)
        for m, day, name in solar_terms:
            if m == d.month and day == d.day:
                label = "明天" if d_offset == 1 else f"{d_offset}天后" if d_offset <= 7 else f"{d.month}月{d.day}日"
                result.append((label, f"🌿 节气 · {name}"))
        for m, day, name in festivals:
            if m == d.month and day == d.day:
                label = "明天" if d_offset == 1 else f"{d_offset}天后" if d_offset <= 7 else f"{d.month}月{d.day}日"
                result.append((label, f"🎉 {name}"))
    return result

def suggestion(t_max, weather):
    if "雷" in weather or "暴" in weather:
        return "🌂 有雷雨，出门带伞，注意安全"
    elif "雨" in weather:
        return "🌂 出门建议带伞，以防阵雨"
    elif t_max >= 35:
        return "🥵 高温预警，注意防暑，多喝水"
    elif t_max >= 33:
        return "😅 气温较高，注意防晒补水"
    elif t_max <= 10:
        return "🧥 气温较低，注意保暖"
    elif "雾" in weather:
        return "🌫 有雾，出行注意安全，减速慢行"
    else:
        return "✅ 天气不错，适合户外活动"

def temp_diff(tv, yv):
    diff = round(tv - yv, 1)
    if diff > 0: return f"↑{diff}°"
    elif diff < 0: return f"↓{abs(diff)}°"
    else: return "→ 持平"

# ====== Telegram 发送 ======
def send_telegram(text):
    if not BOT_TOKEN:
        return {"error": "❌ 请设置 TELEGRAM_BOT_TOKEN 环境变量"}
    if not CHAT_ID:
        return {"error": "❌ 请设置 TELEGRAM_CHAT_ID 环境变量，或在命令行参数传入聊天ID"}
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

# ====== 主函数 ======
def main():
    if not CITY_CODE:
        print("❌ 请设置 WEATHER_CITY_CODE 环境变量")
        sys.exit(1)

    today = date.today()
    try:
        import lunardate
        l = lunardate.LunarDate.from_solar_date(today.year, today.month, today.day)
        lunar_str = f"{lunar_month_names[l.month]} {lunar_day_names[l.day]}"
    except Exception:
        lunar_str = "—"

    # 获取天气
    try:
        forecast, observe = fetch_weather()
    except Exception as e:
        error_msg = f"❌ 获取天气数据失败：{e}"
        send_telegram(error_msg)
        print(error_msg)
        return

    if not forecast:
        print("❌ 未获取到天气数据")
        return

    today_fc = forecast[0]
    cur_temp = observe.get("temp", "")
    cur_humidity = observe.get("humidity", "")
    cur_wind_dir = observe.get("wind_dir", "")
    cur_wind_level = observe.get("wind_level", "")

    today_weather = today_fc["weather"]
    today_max = today_fc["high"]
    today_min = today_fc["low"]
    today_icon = get_icon(today_weather)

    # 昨日对比（从本地缓存读取，默认开启）
    yd_str = ""
    yesterday = load_yesterday()
    if yesterday:
        yd_max, yd_min = yesterday
        yd_str = f"""
<b>━━ 昨日对比</b>
📊 最高温：{yd_max}°C→{today_max}°C {temp_diff(today_max, yd_max)}
📊 最低温：{yd_min}°C→{today_min}°C {temp_diff(today_min, yd_min)}"""

    upcoming = get_upcoming(today)

    # ====== 构建表格 ======
    table = []
    col_w = {"date": 7, "weather": 12, "temp": 12, "wind": 10}
    def cell(content, col):
        return pad_center(content.strip(), col_w[col])
    def row(cells):
        return "|" + "|".join(cell(c, n) for n, c in cells) + "|"
    def sep():
        return "|" + "|".join("-" * col_w[n] for n in col_w) + "|"

    table.append(row([("date","日期"), ("weather","天气"), ("temp","最高↘最低"), ("wind","风力")]))
    table.append(sep())

    for i in range(1, min(7, len(forecast))):
        d = today + timedelta(days=i)
        day_label = d.strftime("%m/%d")
        f = forecast[i]
        icon = get_icon(f["weather"])
        w_text = f"{icon} {f['weather']}".strip()
        if len(w_text) > 12:
            w_text = icon + f["weather"][:6]
        wind = f.get("wind", "")
        # HTML 转义（防止 <3级 被解析为HTML标签）
        wind = wind.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        table.append(row([("date", day_label), ("weather", w_text),
                          ("temp", f"{f['high']}°/{f['low']}°"),
                          ("wind", wind[:10])]))

    table_html = "<pre>" + "\n".join(table) + "</pre>"

    h_bar = "━" * 20

    msg = f"""<b>🌤 早安！天气预报</b>
{h_bar}
📅 今日：{today.year}年{today.month}月{today.day}日  {weekday_map[today.weekday()]}
🏮 农历：{lunar_str}

<b>━━ 今日天气</b>"""

    if cur_temp:
        msg += f"""
🌡 当前温度：{cur_temp}°C"""
    msg += f"""
🌡 最高：{today_max}°C ｜ 最低：{today_min}°C
☀️ 天气：{today_icon} {today_weather}"""
    if cur_humidity:
        msg += f"""
💧 湿度：{cur_humidity}%"""
    if cur_wind_dir:
        msg += f"""
🌬 风向：{cur_wind_dir} {cur_wind_level}级"""

    msg += yd_str

    msg += f"""
{h_bar}
<b>━━ 未来天气趋势</b>
{table_html}

<b>━━ 节气提醒</b>
"""
    # 今日节气
    today_events = []
    for m, day, name in solar_terms:
        if m == today.month and day == today.day:
            today_events.append(f"🌿 今日节气 · {name}")
    for m, day, name in festivals:
        if m == today.month and day == today.day:
            today_events.append(f"🎉 今日 · {name}")

    for ev in today_events:
        msg += f"📌 {ev}\n"

    if upcoming:
        for label, name in upcoming:
            msg += f"📌 {label}：{name}\n"
    if not today_events and not upcoming:
        msg += "📌 未来两周暂无节气或节日\n"

    msg += f"""
<b>━━ 温馨提示</b>
💡 {suggestion(today_max, today_weather)}

{h_bar}
📱 数据来源：中国天气网 · 每日7:00"""

    # 记录今天的天气，供明天对比
    save_today(today_max, today_min)

    return msg.strip()

if __name__ == "__main__":
    msg = main()
    with open("/tmp/weather_report.txt", "w", encoding="utf-8") as f:
        f.write(msg)
    result = send_telegram(msg)
    print(json.dumps(result, ensure_ascii=False, indent=2))