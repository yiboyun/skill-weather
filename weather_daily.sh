#!/bin/sh
# 每日天气预报推送脚本
# 自动定位到脚本所在目录运行
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" && python3 "$DIR/weather_forecast.py" > /dev/null 2>&1