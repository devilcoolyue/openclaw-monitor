#!/bin/bash
# openclaw-monitor 启动脚本

cd "$(dirname "$0")/.."

PORT=10100
LOG_FILE="./monitor.log"
PID_FILE="./monitor.pid"

# Parse arguments
EXTRA_ARGS=""
for arg in "$@"; do
    case "$arg" in
        --tailscale) EXTRA_ARGS="$EXTRA_ARGS --tailscale" ;;
    esac
done

# 检查是否已在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "服务已在运行，PID: $OLD_PID"
        exit 0
    fi
fi

# 启动服务
nohup python3 src/server.py --port $PORT $EXTRA_ARGS >> "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo $NEW_PID > "$PID_FILE"

echo "服务已启动，PID: $NEW_PID，端口: $PORT"
echo "日志文件: $LOG_FILE"
if [[ "$EXTRA_ARGS" == *"--tailscale"* ]]; then
    echo "绑定: Tailscale IP"
fi
