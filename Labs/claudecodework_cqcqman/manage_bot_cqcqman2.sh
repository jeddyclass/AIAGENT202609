#!/bin/bash

SCRIPT_NAME="tg_cqcqman2.py"
LOG_FILE="bot2.log"
MODE_RECORD_FILE=".bot2_mode"
PYTHON_BIN="/home/odneunny/anaconda3/envs/myllm/bin/python"

if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python"
fi

get_pid() {
    pgrep -f "$SCRIPT_NAME"
}

start() {
    TARGET_MODE="$1"
    if [ -z "$TARGET_MODE" ]; then
        if [ -f "$MODE_RECORD_FILE" ]; then
            TARGET_MODE=$(cat "$MODE_RECORD_FILE")
        else
            TARGET_MODE="cloud"
        fi
    fi

    if [ "$TARGET_MODE" != "local" ] && [ "$TARGET_MODE" != "cloud" ]; then
        echo "❌ 錯誤：未知的模式 '$TARGET_MODE'！"
        exit 1
    fi

    PID=$(get_pid)
    if [ -n "$PID" ]; then
        echo "⚠️ 服務已在運行中 (PID: $PID)"
    else
        echo "🚀 啟動 Telegram Bot (模式: $TARGET_MODE)..."
        echo "$TARGET_MODE" > "$MODE_RECORD_FILE"
        nohup $PYTHON_BIN $SCRIPT_NAME --mode "$TARGET_MODE" > $LOG_FILE 2>&1 &
        sleep 2
        PID=$(get_pid)
        if [ -n "$PID" ]; then
            echo "✅ 啟動成功！PID: $PID"
        else
            echo "❌ 啟動失敗，請檢查 $LOG_FILE"
        fi
    fi
}

stop() {
    PID=$(get_pid)
    if [ -n "$PID" ]; then
        echo "🛑 正在停止服務 (PID: $PID)..."
        kill -15 $PID
        sleep 2
        if [ -n "$(get_pid)" ]; then kill -9 $PID; fi
        echo "✅ 服務已停止。"
    else
        echo "ℹ️ 未發現運行中的服務。"
    fi
}

case "$1" in
    start)
        start "$2"
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 1
        start "$2"
        ;;
    status)
        PID=$(get_pid)
        MODE=$(cat "$MODE_RECORD_FILE" 2>/dev/null || echo "未知")
        if [ -n "$PID" ]; then
            echo "🟢 狀態：運行中 (PID: $PID) | 模式: $MODE"
        else
            echo "🔴 狀態：未運行"
        fi
        ;;
    logs)
        tail -n 50 -f $LOG_FILE
        ;;
    cli)
        TARGET_MODE="${2:-cloud}"
        echo "💻 進入 ADK CLI 除錯交談 [模式: $TARGET_MODE] (Ctrl+C 退出)..."
        export RUN_MODE="$TARGET_MODE"
        $PYTHON_BIN -m google.adk.cli run .
        ;;
    web)
        TARGET_MODE="${2:-cloud}"
        echo "🌐 啟動 ADK 視覺化除錯介面 [模式: $TARGET_MODE] (預設 8501 埠號)..."
        export RUN_MODE="$TARGET_MODE"
        $PYTHON_BIN -m google.adk.cli web --host 0.0.0.0 --port 8899 .
        ;;
    *)
        echo "用法: $0 {start [cloud|local]|stop|restart|status|logs|cli|web}"
        exit 1
        ;;
esac