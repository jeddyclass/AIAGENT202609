#!/bin/bash

# 定義檔案名稱與你的 Python 環境
SCRIPT_NAME="tg_cqcqman.py"
LOG_FILE="bot.log"
MODE_RECORD_FILE=".bot_mode"
PYTHON_BIN="/home/odneunny/anaconda3/envs/myllm/bin/python"

if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python"
fi

get_pid() {
    pgrep -f "$SCRIPT_NAME"
}

start() {
    TARGET_MODE="$1"

    # 若沒有帶入參數，自動尋找上一次的模式，預設為 cloud
    if [ -z "$TARGET_MODE" ]; then
        if [ -f "$MODE_RECORD_FILE" ]; then
            TARGET_MODE=$(cat "$MODE_RECORD_FILE")
        else
            TARGET_MODE="cloud"
        fi
    fi

    # 參數防呆檢測
    if [ "$TARGET_MODE" != "local" ] && [ "$TARGET_MODE" != "cloud" ]; then
        echo "❌ 錯誤：未知的模式 '$TARGET_MODE'！"
        echo "正確用法: $0 start local  或  $0 start cloud"
        exit 1
    fi

    PID=$(get_pid)
    if [ -n "$PID" ]; then
        CURRENT_MODE=$(cat "$MODE_RECORD_FILE" 2>/dev/null || echo "未知")
        echo "⚠️ 服務已經在運行中 (PID: $PID, 目前模式: $CURRENT_MODE)"
        echo "💡 若要切換模式，請執行: $0 restart $TARGET_MODE"
    else
        echo "🚀 正在以後台模式啟動 AI Agent (模式: $TARGET_MODE)..."
        echo "$TARGET_MODE" > "$MODE_RECORD_FILE"
        nohup $PYTHON_BIN $SCRIPT_NAME --mode "$TARGET_MODE" > $LOG_FILE 2>&1 &
        sleep 2
        PID=$(get_pid)
        if [ -n "$PID" ]; then
            echo "✅ 啟動成功！PID: $PID [模式: $TARGET_MODE]"
            echo "📄 查閱日誌請輸入: $0 logs"
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
        if [ -n "$(get_pid)" ]; then
            kill -9 $PID
        fi
        echo "✅ 服務已停止。"
    else
        echo "ℹ️ 未發現運行中的服務。"
    fi
}

status() {
    PID=$(get_pid)
    CURRENT_MODE=$(cat "$MODE_RECORD_FILE" 2>/dev/null || echo "未知")
    if [ -n "$PID" ]; then
        echo "🟢 狀態：運行中 (PID: $PID) | 運行引擎: 【$CURRENT_MODE】"
    else
        echo "🔴 狀態：未運行 (上次模式: $CURRENT_MODE)"
    fi
}

logs() {
    tail -n 50 -f $LOG_FILE
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
        status
        ;;
    logs)
        logs
        ;;
    *)
        echo "使用說明:"
        echo "  $0 start cloud    # 啟動並使用 Google Gemini 雲端算力 (預設)"
        echo "  $0 start local    # 啟動並使用地端 OpenWebUI 算力"
        echo "  $0 stop           # 停止服務"
        echo "  $0 restart cloud  # 停止並以 Cloud 模式重啟"
        echo "  $0 status         # 查看當前運行模式與 PID"
        echo "  $0 logs           # 即時查看 Log"
        exit 1
        ;;
esac