#!/bin/bash
# Edu-Companion Nginx 统一网关启动脚本
# 用法: ./start.sh [start|stop|reload]

DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$DIR/nginx.pid"

case "${1:-start}" in
  start)
    echo "Starting Nginx (edu-companion)..."
    /usr/sbin/nginx -c "$DIR/nginx.conf" -p "$DIR"
    echo "  PID: $(cat "$PIDFILE" 2>/dev/null || echo '?')"
    echo "  URL: http://0.0.0.0:8080"
    ;;
  stop)
    echo "Stopping Nginx..."
    /usr/sbin/nginx -c "$DIR/nginx.conf" -p "$DIR" -s stop
    echo "  stopped"
    ;;
  reload)
    echo "Reloading Nginx..."
    /usr/sbin/nginx -c "$DIR/nginx.conf" -p "$DIR" -s reload
    echo "  reloaded"
    ;;
  *)
    echo "Usage: $0 [start|stop|reload]"
    exit 1
    ;;
esac
