#!/bin/bash

SERVICE_NAME="openclaw-gateway"

usage() {
    echo "Usage: $0 {start|stop|restart|status|logs|help}"
    echo ""
    echo "Commands:"
    echo "  start    启动服务"
    echo "  stop     停止服务"
    echo "  restart  重启服务"
    echo "  status   查看服务状态"
    echo "  logs     查看实时日志 (Ctrl+C 退出)"
    echo "  help     显示帮助信息"
}

case "$1" in
    start)
        echo "Starting $SERVICE_NAME..."
        systemctl --user start "$SERVICE_NAME"
        systemctl --user status "$SERVICE_NAME" --no-pager
        ;;
    stop)
        echo "Stopping $SERVICE_NAME..."
        systemctl --user stop "$SERVICE_NAME"
        echo "$SERVICE_NAME stopped."
        ;;
    restart)
        echo "Restarting $SERVICE_NAME..."
        systemctl --user restart "$SERVICE_NAME"
        systemctl --user status "$SERVICE_NAME" --no-pager
        ;;
    status)
        systemctl --user status "$SERVICE_NAME"
        ;;
    logs)
        echo "Showing logs for $SERVICE_NAME (Ctrl+C to exit)..."
        journalctl --user -u "$SERVICE_NAME" -f
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        usage
        exit 1
        ;;
esac
