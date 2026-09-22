# tg_cqcqman2.py
import os
import logging
import argparse
from datetime import datetime, time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.request import HTTPXRequest

# 引入核心 Agent 推論函式
from agent import run_agent_query

parser = argparse.ArgumentParser(description="Telegram Connector for ADK Agent")
parser.add_argument("--mode", choices=["local", "cloud"], default="cloud", help="運行模式: local 或 cloud")
args, _ = parser.parse_known_args()
RUN_MODE = args.mode

load_dotenv()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("TG_Connector")
logging.getLogger("httpx").setLevel(logging.WARNING)

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = int(os.getenv("TG_CHAT_ID", "0"))
APP_TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Asia/Taipei"))

SCHEDULE_TIMES_RAW = os.getenv("SCHEDULE_TIMES", "04:45, 08:45, 11:45, 16:45, 21:45")
PARSED_SCHEDULE_TIMES = []
for t_str in SCHEDULE_TIMES_RAW.split(","):
    t_str = t_str.strip()
    if not t_str: continue
    try:
        h, m = map(int, t_str.split(":"))
        PARSED_SCHEDULE_TIMES.append((h, m))
    except ValueError:
        logger.error(f"⚠️ 無法解析排程時間: {t_str}")

async def safe_send_message(bot, chat_id, text, reply_to_message_id=None, max_messages=3):
    chunk_size = 3800
    chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    is_truncated = len(chunks) > max_messages
    for idx, chunk in enumerate(chunks[:max_messages]):
        current_text = chunk + ("\n\n⚠️ *內容超長... 僅就前述回覆.*" if is_truncated and idx == max_messages-1 else "")
        try:
            await bot.send_message(
                chat_id=chat_id, 
                text=current_text, 
                parse_mode="Markdown", 
                disable_web_page_preview=True, 
                reply_to_message_id=reply_to_message_id if idx == 0 else None
            )
        except Exception:
            plain_text = current_text.replace("*", "").replace("`", "")
            await bot.send_message(
                chat_id=chat_id, 
                text=plain_text, 
                disable_web_page_preview=True, 
                reply_to_message_id=reply_to_message_id if idx == 0 else None
            )

def get_slot_name(hour: int) -> str:
    if 3 <= hour < 6: return "歐美盤後與跨大西洋焦點"
    elif 6 <= hour < 10: return "晨間開盤前瞻"
    elif 10 <= hour < 13: return "午間盤中動態"
    elif 13 <= hour < 18: return "午後盤後精要"
    return "夜間全球焦點"

async def scheduled_push_job(context: ContextTypes.DEFAULT_TYPE):
    now_dt = datetime.now(APP_TIMEZONE)
    today_str = now_dt.strftime("%Y-%m-%d %H:%M")
    slot_name = get_slot_name(now_dt.hour)
    
    await context.bot.send_message(
        chat_id=TG_CHAT_ID, 
        text=f"🤖 *ADK Agent ({RUN_MODE.upper()}):* 檢索生成【{slot_name}】日報...", 
        parse_mode="Markdown"
    )
    
    region = "western" if 3 <= now_dt.hour < 6 else "global"
    prompt = f"""請調用 `fetch_latest_market_overview(focus_region="{region}")` 撰寫【{slot_name}】深度財經日報。
包含重點：
1. *【收盤總經與宏觀綜述】*
2. *【關鍵新聞深度解讀】* (標註來源與連結)
3. *【科技巨頭與 AI 供應鏈動向】*
4. *💡 開盤前瞻與宏觀風控指標*
"""
    report = run_agent_query(prompt, mode=RUN_MODE)
    await safe_send_message(context.bot, TG_CHAT_ID, f"📊 *【{slot_name}】趨勢綜述 ({today_str})*\n\n{report}")

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = " ".join(context.args).strip()
    if not user_input:
        await update.message.reply_text("💡 請輸入專題關鍵字，例如: `/ask tsmc` 或 `/ask 台積電`", parse_mode="Markdown")
        return
    
    await update.message.reply_text(f"🔍 [{RUN_MODE.upper()}] 正在檢索「{user_input}」深度專題...")
    prompt = f"""使用者指定專題「{user_input}」。
請調用 `search_finance_rss(keyword="{user_input}")` 取得即時新聞。
輸出繁體中文分析：
1. *【{user_input} - 全球局勢與核心動態綜述】*
2. *【重點新聞深度解讀】*
3. *【產業鏈上下游影響盤點】*
4. *💡 首席投資經理操作展望與風控提示*
"""
    report = run_agent_query(prompt, mode=RUN_MODE)
    today_str = datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d %H:%M")
    await safe_send_message(context.bot, update.effective_chat.id, f"💡 *【專題分析】{user_input} ({today_str})*\n\n{report}", reply_to_message_id=update.message.message_id)

async def cq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = " ".join(context.args).strip()
    if not user_query:
        await update.message.reply_text(f"💡 請輸入問句，例如: `/cq 現在台積電的營收展望如何？`", parse_mode="Markdown")
        return
    
    await update.message.reply_text(f"🧠 [{RUN_MODE.upper()}] 思考檢索中：「*{user_query}*」...", parse_mode="Markdown")
    prompt = f"""使用者提問：「{user_query}」
1. 提煉標的並調用 `search_finance_rss` 獲取真實資料。
2. 針對疑問給予專業解答並引用最新新聞來源。
"""
    report = run_agent_query(prompt, mode=RUN_MODE)
    today_str = datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d %H:%M")
    await safe_send_message(context.bot, update.effective_chat.id, f"💬 *【解答】({today_str})*\n❓ *問題*：{user_query}\n\n{report}", reply_to_message_id=update.message.message_id)

def main():
    request = HTTPXRequest(connect_timeout=120.0, read_timeout=120.0, write_timeout=120.0, connection_pool_size=8)
    app = Application.builder().token(TG_BOT_TOKEN).request(request).build()
    
    for h, m in PARSED_SCHEDULE_TIMES:
        app.job_queue.run_daily(scheduled_push_job, time=time(h, m, 0, tzinfo=APP_TIMEZONE))

    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CommandHandler("cq", cq_command))
    
    logger.info(f"⚡ Telegram 機器人上線 (模式: {RUN_MODE.upper()})...")
    app.run_polling(bootstrap_retries=5)

if __name__ == "__main__":
    main()