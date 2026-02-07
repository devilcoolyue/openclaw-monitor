#!/bin/bash
# openclaw-monitor 启动脚本（通过 systemd 用户服务）

SERVICE_NAME="openclaw-monitor"

# 检查 systemd 用户服务是否已安装
if systemctl --user cat "$SERVICE_NAME" &>/dev/null; then
    # 检查是否已在运行
    if systemctl --user is-active --quiet "$SERVICE_NAME"; then
        echo "服务已在运行"
        systemctl --user status "$SERVICE_NAME" --no-pager
        exit 0
    fi

    # 通过 systemd 启动服务
    systemctl --user start "$SERVICE_NAME"
    echo "服务已通过 systemd 启动"
    echo ""
    echo "  查看状态: systemctl --user status $SERVICE_NAME"
    echo "  查看日志: journalctl --user -u $SERVICE_NAME -f"
    echo "  停止服务: systemctl --user stop $SERVICE_NAME"
else
    # 回退：systemd 服务未安装，使用传统方式启动
    echo "systemd 用户服务未安装，使用传统方式启动..."
    echo "建议运行 ./scripts/install.sh 安装 systemd 服务"
    echo ""

    cd "$(dirname "$0")/.."

    PORT="${OPENCLAW_MONITOR_PORT:-18765}"
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
fi
