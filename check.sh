#!/bin/bash
# openclaw-monitor 进程检查脚本（用于 crontab）

cd "$(dirname "$0")"

PID_FILE="./monitor.pid"
LOG_FILE="./monitor.log"

# 检查进程是否存在
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        exit 0  # 进程正常运行
    fi
fi

# 进程不存在，重新启动
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 检测到服务未运行，正在重启..." >> "$LOG_FILE"
./start.sh >> "$LOG_FILE" 2>&1
