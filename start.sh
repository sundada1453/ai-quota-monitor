#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$DIR/widget.pid"
LOG_FILE="$DIR/widget.log"

export DISPLAY="${DISPLAY:-:2}"

start() {
    # 检查是否已在运行
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "AI Quota Monitor 已经在运行中 (PID: $(cat "$PID_FILE"))"
        return 0
    fi
    pkill -f "ai-quota-monitor/widget.py" 2>/dev/null || true

    echo "正在启动 AI Quota Monitor 悬浮窗 (DISPLAY=$DISPLAY)..."
    cd "$DIR"
    setsid -f /usr/bin/python3 -u "$DIR/widget.py" >> "$LOG_FILE" 2>&1
    sleep 1
    PID=$(pgrep -f "ai-quota-monitor/widget.py" | head -n 1)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        echo "$PID" > "$PID_FILE"
        echo "启动成功！(PID: $PID)"
    else
        echo "启动可能异常，请检查日志: $LOG_FILE"
        cat "$LOG_FILE"
    fi
}

stop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        echo "正在停止 AI Quota Monitor (PID: $PID)..."
        kill "$PID" 2>/dev/null
        rm -f "$PID_FILE"
    fi
    pkill -f "ai-quota-monitor/widget.py" 2>/dev/null || true
    echo "已停止。"
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "AI Quota Monitor 运行正常 (PID: $(cat "$PID_FILE"))"
    elif pgrep -f "ai-quota-monitor/widget.py" >/dev/null; then
        echo "AI Quota Monitor 正在运行 (PID: $(pgrep -f "ai-quota-monitor/widget.py" | tr '\n' ' '))"
    else
        echo "AI Quota Monitor 未运行"
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    status)
        status
        ;;
    *)
        start
        ;;
esac
