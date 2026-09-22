# pip install --upgrade "google-adk>=2.0.0" python-telegram-bot feedparser python-dotenv httpx

import os
import sys
import json
import logging
import argparse
import feedparser
from datetime import datetime, time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Telegram 模組
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.request import HTTPXRequest

# Google ADK 2.0 模組
from google.adk.agents import Agent
from google import genai
from google.genai import types

# 本地相容客戶端 (連線 OpenWebUI)
from openai import OpenAI

# 1. 參數解析與環境載入
parser = argparse.ArgumentParser(description="Telegram Finance Unified ADK 2.0 Service")
parser.add_argument("--mode", choices=["local", "cloud"], default="cloud", help="運行模式: local 或 cloud")
args, _ = parser.parse_known_args()
RUN_MODE = args.mode

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger("ADK2_FinanceService")
logging.getLogger("httpx").setLevel(logging.WARNING)

logger.info(f"🚀 Google ADK 2.0 服務啟動模式: 【{RUN_MODE.upper()}】")

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = int(os.getenv("TG_CHAT_ID", "0"))
APP_TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Asia/Taipei"))

SCHEDULE_TIMES_RAW = os.getenv("SCHEDULE_TIMES", "04:30, 08:30, 11:30, 16:15, 21:00")
PARSED_SCHEDULE_TIMES = []
for t_str in SCHEDULE_TIMES_RAW.split(","):
    t_str = t_str.strip()
    if not t_str:
        continue
    try:
        h, m = map(int, t_str.split(":"))
        PARSED_SCHEDULE_TIMES.append((h, m))
    except ValueError:
        logger.error(f"⚠️ 無法解析時間格式: {t_str}")

FINANCE_FEEDS = {
    "鉅亨網 (台股焦點)": "https://news.cnyes.com/rss/category/tw_stock",
    "鉅亨網 (國際政經)": "https://news.cnyes.com/rss/category/headline",
    "Yahoo 財經 (台股即時)": "https://tw.stock.yahoo.com/rss?category=tw-market",
    "經濟日報 (證券焦點)": "https://money.udn.com/rssfeed/news/1001/5590",
    "工商時報 (科技產業)": "https://www.ctee.com.tw/rss/category/tech",
    "MoneyDJ 理財網": "https://www.moneydj.com/KMDJ/rss/NewsRss.aspx",
    "科技新報 (TechNews)": "https://technews.tw/feed/",
    "CNBC Top Stories": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "MarketWatch Top Stories": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "WSJ Markets News": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "Yahoo Finance US": "https://finance.yahoo.com/news/rssindex",
    "TechCrunch (AI/Enterprise)": "https://techcrunch.com/category/artificial-intelligence/feed/"
}

# 2. 工具定義 (符合 ADK 2.0 標準 Python 函式規範，具備型別與 Docstring)
def search_finance_rss(keyword: str) -> str:
    """在各大財經 RSS 來源中檢索新聞（內建實體提煉與同義詞擴展）。
    
    Args:
        keyword: 檢索標的名稱或關鍵字
    """
    logger.info(f"🛠️ [ADK 2.0 Tool] 執行 search_finance_rss: '{keyword}'")
    articles = []
    kw_raw = keyword.strip().lower()

    stop_words = ["現在", "買", "好嗎", "可以在", "短期內", "取得", "足夠的", "回報嗎", "如何", 
                  "怎麼樣", "請分析", "分析", "最近", "今天", "消息", "投資", "建議"]
    
    alias_dict = {
        "tsmc": ["tsmc", "台積電", "2330", "晶圓代工", "taiwan semiconductor"],
        "台積電": ["台積電", "tsmc", "2330", "晶圓代工", "先進製程", "cowos"],
        "ai": ["ai", "人工智慧", "llm", "算力", "伺服器", "深度學習", "大模型", "生成式"],
        "人工智慧": ["人工智慧", "ai", "llm", "算力", "伺服器", "深度學習", "大模型"],
        "nvidia": ["nvidia", "輝達", "nvda", "黃仁勳", "cuda", "gpu", "blackwell"],
        "輝達": ["輝達", "nvidia", "nvda", "黃仁勳", "cuda", "gpu", "blackwell"],
        "fed": ["fed", "聯準會", "美聯儲", "powell", "fomc", "降息", "升息", "利率"],
        "聯準會": ["聯準會", "美聯儲", "fed", "powell", "fomc", "降息", "升息", "利率"]
    }

    matched_entity = None
    for entity in alias_dict.keys():
        if entity in kw_raw:
            matched_entity = entity
            break

    if matched_entity:
        search_terms = alias_dict[matched_entity]
    else:
        cleaned_kw = kw_raw
        for sw in stop_words:
            cleaned_kw = cleaned_kw.replace(sw, " ")
        cleaned_kw = " ".join(cleaned_kw.split())
        search_terms = [cleaned_kw] if cleaned_kw else [kw_raw]

    for source, url in FINANCE_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                title = getattr(entry, "title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link = getattr(entry, "link", "")
                text_to_check = f"{title} {summary}".lower()

                if any(term in text_to_check for term in search_terms):
                    articles.append(f"來源: {source}\n標題: {title}\n概述: {summary}\n連結: {link}\n---")
        except Exception as e:
            logger.warning(f"解析 {source} 失敗: {e}")

    return "\n".join(articles[:40]) if articles else f"各大財經新聞中未檢索到與 '{keyword}' 相關報導。"


def fetch_latest_market_overview(focus_region: str = "global") -> str:
    """抓取最新市場綜合焦點新聞。
    
    Args:
        focus_region: 聚焦區域，可為 'global' 或 'western'
    """
    logger.info(f"🛠️ [ADK 2.0 Tool] 執行 fetch_latest_market_overview (區域: {focus_region})")
    articles = []
    
    if focus_region == "western":
        priority_sources = ["CNBC Top Stories", "MarketWatch Top Stories", "WSJ Markets News", "Yahoo Finance US"]
    else:
        priority_sources = ["鉅亨網 (台股焦點)", "鉅亨網 (國際政經)", "Yahoo 財經 (台股即時)", "CNBC Top Stories"]

    for source in priority_sources:
        url = FINANCE_FEEDS.get(source)
        if not url:
            continue
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:6]:
                title = getattr(entry, "title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link = getattr(entry, "link", "")
                articles.append(f"來源: {source}\n標題: {title}\n概述: {summary}\n連結: {link}\n---")
        except Exception as e:
            logger.warning(f"解析 {source} 失敗: {e}")

    return "\n".join(articles[:50]) if articles else "目前無法獲取即時市場頭條。"

AVAILABLE_TOOLS = [search_finance_rss, fetch_latest_market_overview]
TOOL_DISPATCH_MAP = {fn.__name__: fn for fn in AVAILABLE_TOOLS}

# 3. 生命週期鉤子 (ADK 2.0 Callbacks)
def before_agent_hook(context):
    agent_name = getattr(context, "agent_name", "FinanceAgent")
    logger.info(f"⚡ [ADK 2.0 Node Hook] 進入 Agent 節點: {agent_name}")

def after_agent_hook(context):
    agent_name = getattr(context, "agent_name", "FinanceAgent")
    logger.info(f"✅ [ADK 2.0 Node Hook] 完成 Agent 節點執行: {agent_name}")

SYSTEM_INSTRUCTION = """你是一位資深的避險基金分析師與全球半導體/科技投資總監。
你的職責是自主調用工具獲取客觀真實的財經資訊，並以繁體中文撰寫深度專業分析。

排版規範：
1. 嚴禁使用 Markdown 標題符號（嚴禁出現 #, ##, ###）。
2. 標題請一律使用 emoji 搭配單星號粗體，例如：*【核心結論】*。
3. 粗體一律使用單星號：*重點文字*。
4. 連結格式：[新聞中文標題](新聞網址)。
"""

# 4. 初始化客戶端與 ADK 2.0 Agent
if RUN_MODE == "cloud":
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    ACTIVE_MODEL = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
    if not GEMINI_API_KEY:
        raise ValueError("❌ 雲端模式缺少 GEMINI_API_KEY！")
    
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
    cloud_client = genai.Client(api_key=GEMINI_API_KEY)
    
    # ADK 2.0 原生 Agent 宣告（直接傳遞模型字串與工具清單）
    adk_agent = Agent(
        name="finance_director_agent",
        model=ACTIVE_MODEL,
        instruction=SYSTEM_INSTRUCTION,
        tools=AVAILABLE_TOOLS
    )
else:
    OPENWEBUI_BASE_URL = os.getenv("OPENWEBUI_BASE_URL", "http://172.10.0.22:8080/api")
    OPENWEBUI_API_KEY = os.getenv("OPENWEBUI_API_KEY", "sk-abc")
    ACTIVE_MODEL = os.getenv("LOCAL_MODEL_NAME", "gemma4:12b")
    local_client = OpenAI(base_url=OPENWEBUI_BASE_URL, api_key=OPENWEBUI_API_KEY)

def clean_markdown_headings(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            lines.append(f"\n*{stripped.lstrip('#').strip()}*")
        else:
            lines.append(line)
    return "\n".join(lines)

async def run_adk_service(user_id: str, prompt: str) -> str:
    """執行 Agent 服務，支援原生工具調度與生命週期日誌"""
    try:
        before_agent_hook(type("Context", (), {"agent_name": "finance_director_agent"}))
        
        if RUN_MODE == "cloud":
            # 雲端：由 Google GenAI 原生自動處理 Tool Calling 迴圈
            response = cloud_client.models.generate_content(
                model=ACTIVE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=AVAILABLE_TOOLS,
                    temperature=0.2
                )
            )
            final_text = response.text or ""
        else:
            # 地端：OpenWebUI 標準 Tool Calling 協定
            tools_spec = [
                {
                    "type": "function",
                    "function": {
                        "name": "search_finance_rss",
                        "description": "在各大財經 RSS 來源中檢索新聞",
                        "parameters": {
                            "type": "object",
                            "properties": {"keyword": {"type": "string", "description": "標的名稱或關鍵字"}},
                            "required": ["keyword"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "fetch_latest_market_overview",
                        "description": "抓取最新市場綜合焦點新聞",
                        "parameters": {
                            "type": "object",
                            "properties": {"focus_region": {"type": "string", "enum": ["global", "western"]}},
                            "required": []
                        }
                    }
                }
            ]
            
            messages = [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt}
            ]
            
            response = local_client.chat.completions.create(
                model=ACTIVE_MODEL,
                messages=messages,
                tools=tools_spec,
                temperature=0.2
            )
            
            choice = response.choices[0].message
            if choice.tool_calls:
                messages.append(choice)
                for call in choice.tool_calls:
                    fn_name = call.function.name
                    args = json.loads(call.function.arguments or "{}")
                    fn = TOOL_DISPATCH_MAP.get(fn_name)
                    obs = fn(**args) if fn else "找不到對應工具"
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": str(obs)
                    })
                
                final_res = local_client.chat.completions.create(
                    model=ACTIVE_MODEL,
                    messages=messages,
                    temperature=0.2
                )
                final_text = final_res.choices[0].message.content or ""
            else:
                final_text = choice.content or ""
        
        after_agent_hook(type("Context", (), {"agent_name": "finance_director_agent"}))
        return clean_markdown_headings(final_text) if final_text else "⚠️ 未返回有效文字分析。"

    except Exception as e:
        logger.error(f"❌ 工作流執行異常: {e}", exc_info=True)
        return f"❌ Agent 處理異常 ({RUN_MODE.upper()}): {e}"

# 5. Telegram 介面與排程邏輯
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
    logger.info(f"⏰ 觸發定時任務: {slot_name} ({today_str})")
    
    await context.bot.send_message(
        chat_id=TG_CHAT_ID, 
        text=f"🤖 *ADK Agent ({RUN_MODE.upper()}):* 檢索生成【{slot_name}】日報...", 
        parse_mode="Markdown"
    )
    
    region = "western" if 3 <= now_dt.hour < 6 else "global"
    scheduled_prompt = f"""請調用 `fetch_latest_market_overview(focus_region="{region}")` 撰寫【{slot_name}】深度財經日報。
包含重點：
1. *【收盤總經與宏觀綜述】*
2. *【關鍵新聞深度解讀】* (標註來源名稱與新聞連結)
3. *【科技巨頭與 AI 供應鏈動向】*
4. *💡 開盤前瞻與宏觀風控指標*
"""
    report = await run_adk_service(user_id=f"scheduled_{TG_CHAT_ID}", prompt=scheduled_prompt)
    await safe_send_message(
        context.bot, 
        TG_CHAT_ID, 
        f"📊 *【{slot_name}】趨勢綜述 ({today_str})*\n\n{report}", 
        max_messages=3
    )

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = " ".join(context.args).strip()
    if not user_input:
        await update.message.reply_text("💡 請輸入專題關鍵字，例如: `/ask tsmc` 或 `/ask 台積電`", parse_mode="Markdown")
        return
    
    await update.message.reply_text(f"🔍 [{RUN_MODE.upper()}] 正在檢索「{user_input}」深度專題...")
    ask_prompt = f"""使用者指定專題「{user_input}」。
請調用 `search_finance_rss(keyword="{user_input}")` 取得即時新聞。
根據檢索到的資訊輸出繁體中文報告，包含：
1. *【{user_input} - 全球局勢與核心動態綜述】*
2. *【重點新聞深度解讀】* (列出來源媒體、新聞標題與超連結)
3. *【產業鏈上下游影響盤點】*
4. *💡 首席投資經理操作展望與風控提示*
"""
    report = await run_adk_service(user_id=str(update.effective_chat.id), prompt=ask_prompt)
    today_str = datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d %H:%M")
    await safe_send_message(
        context.bot, 
        update.effective_chat.id, 
        f"💡 *【專題分析】{user_input} ({today_str})*\n\n{report}", 
        reply_to_message_id=update.message.message_id
    )

async def cq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = " ".join(context.args).strip()
    user_id = update.effective_chat.id
    if not user_query:
        await update.message.reply_text(f"💡 *智能問答 (/cq)*\n請輸入自然問句，例如: `/cq 現在台積電的營收展望如何？`", parse_mode="Markdown")
        return
    
    await update.message.reply_text(f"🧠 [{RUN_MODE.upper()}] 正在思考檢索：「*{user_query}*」...", parse_mode="Markdown")
    
    cq_prompt = f"""使用者提問：「{user_query}」
【操作指令】：
1. 請先提煉核心標的並調用 `search_finance_rss` 獲取真實資料。
2. 針對使用者的疑問進行深入的繁體中文解答。
3. 報告中引用最新事實並附帶來源與新聞連結。
"""
    report = await run_adk_service(user_id=str(user_id), prompt=cq_prompt)
    today_str = datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d %H:%M")
    await safe_send_message(
        context.bot, 
        update.effective_chat.id, 
        f"💬 *【解答】({today_str})*\n❓ *問題*：{user_query}\n\n{report}", 
        reply_to_message_id=update.message.message_id
    )

def main():
    request = HTTPXRequest(connect_timeout=120.0, read_timeout=120.0, write_timeout=120.0, connection_pool_size=8)
    app = Application.builder().token(TG_BOT_TOKEN).request(request).build()
    
    for h, m in PARSED_SCHEDULE_TIMES:
        app.job_queue.run_daily(scheduled_push_job, time=time(h, m, 0, tzinfo=APP_TIMEZONE))
        logger.info(f"📅 定時排程掛載: {h:02d}:{m:02d}")

    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CommandHandler("cq", cq_command))
    
    logger.info(f"⚡ Telegram 服務監聽中 (模式: {RUN_MODE.upper()})...")
    app.run_polling(bootstrap_retries=5)

if __name__ == "__main__":
    main()