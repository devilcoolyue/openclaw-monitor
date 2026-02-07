#!/bin/bash
# openclaw-monitor 健康检查脚本

SERVICE_NAME="openclaw-monitor"

# 检查 systemd 用户服务是否已安装
if systemctl --user cat "$SERVICE_NAME" &>/dev/null; then
    # 通过 systemd 检查服务状态
    if systemctl --user is-active --quiet "$SERVICE_NAME"; then
        echo "✓ 服务运行正常"
        exit 0
    else
        echo "✗ 服务未运行，正在重启..."
        systemctl --user restart "$SERVICE_NAME"
        sleep 2
        if systemctl --user is-active --quiet "$SERVICE_NAME"; then
            echo "✓ 服务已重新启动"
            exit 0
        else
            echo "✗ 服务重启失败"
            systemctl --user status "$SERVICE_NAME" --no-pager
            exit 1
        fi
    fi
else
    # 回退：传统 PID 检查方式
    cd "$(dirname "$0")/.."

    PID_FILE="./monitor.pid"
    LOG_FILE="./monitor.log"

    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            exit 0  # 进程正常运行
        fi
    fi

    # 进程不存在，重新启动
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 检测到服务未运行，正在重启..." >> "$LOG_FILE"
    ./scripts/start.sh >> "$LOG_FILE" 2>&1
fi
