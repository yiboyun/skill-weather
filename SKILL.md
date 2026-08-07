---
description: Use this skill to set up or run a daily weather forecast for any city
  in China to Telegram. Triggers when the user mentions daily weather push, cron weather
  job, or wants to recreate the weather script after server migration. Fetches data
  from China Weather Network (weather.com.cn) official API and sends via Telegram bot.
name: weather
---

# Daily Weather Forecast (天气预报)

Send a formatted daily weather forecast for a configured city to Telegram, using China Weather Network (weather.com.cn) official data. Includes today's weather, self-recorded yesterday comparison, 7-day outlook, lunar calendar, solar terms, and lifestyle tips.

> 🔒 **No location is hardcoded.** All config (city, token, chat ID) comes from environment variables.

## Prerequisites

```bash
pip install lunardate   # optional; if missing, lunar date shows "—"
```

## Quick Start

Base URL: `https://raw.githubusercontent.com/yiboyun/skill-weather/refs/heads/main/`

```bash
# 下载脚本
mkdir -p skills/weather-forecast
curl -o skills/weather-forecast/weather_forecast.py https://raw.githubusercontent.com/yiboyun/skill-weather/refs/heads/main/weather_forecast.py
curl -o skills/weather-forecast/weather_daily.sh https://raw.githubusercontent.com/yiboyun/skill-weather/refs/heads/main/weather_daily.sh
chmod +x skills/weather-forecast/weather_daily.sh

# 配置环境变量（请向用户询问以下三项）
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
export WEATHER_CITY_CODE="your_city_code"

# 测试运行
python3 skills/weather-forecast/weather_forecast.py
```

### One-time run

```bash
cd <skill_dir>
python3 weather_forecast.py            # uses env vars
python3 weather_forecast.py 123456789  # or pass chat ID as CLI arg
```

### Cron job (daily at 7:00 AM)

```bash
qwenpaw cron create \
  --name "每日天气预报" \
  --schedule "0 7 * * *" \
  --timezone "Asia/Shanghai" \
  --agent-id default \
  --text "请执行 skills/weather-forecast/weather_daily.sh，生成并发送当日天气预报到 Telegram。完成后告诉我结果即可。"
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Telegram bot token |
| `TELEGRAM_CHAT_ID` | ✅ | Target chat ID (can also pass as CLI arg) |
| `WEATHER_CITY_CODE` | ✅ | weather.com.cn city code, e.g. 101120709 |

> 💡 Yesterday comparison is **self-recorded**: the script saves today's temps to a local file (`.weather_yesterday.json`) each run, and reads it next day. No external API, no coordinates needed. First day simply has no comparison.

## Output Format

- **Header**: Greeting, date, lunar calendar date
- **Today's Weather**: Current temp, high/low, condition, humidity, wind
- **Yesterday Comparison**: High/low change vs self-recorded yesterday
- **7-Day Forecast Table**: Date, weather icon, high/low, wind
- **Solar Terms & Festivals**: Today's and upcoming events within 14 days
- **Lifestyle Tip**: Weather-appropriate suggestion

## Data Source

- **7-day forecast + current obs**: China Weather Network (weather.com.cn) via city code
- **Yesterday comparison**: self-recorded local cache (`.weather_yesterday.json`)

## Files

- `weather_forecast.py` — Main Python script (no external deps except optional `lunardate`)
- `weather_daily.sh` — Shell wrapper that auto-detects the script directory

## Notes

- **Security**: No sensitive data hardcoded. All config from env vars.
- **Privacy**: No location exposed in this document.
- HTML-escapes wind info (e.g. `&lt;3级`) to avoid Telegram parse errors.
- On fetch failure, sends an error message to Telegram instead of crashing.