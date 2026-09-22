# agent.py
# pip install litellm
import os
import json
import logging
import feedparser
from dotenv import load_dotenv

from google.adk.agents import Agent
from google import genai
from google.genai import types
from openai import OpenAI

load_dotenv()
logger = logging.getLogger("ADK_FinanceAgent")

# ── 1. 財經 RSS 來源清單 ──
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

# ── 2. ADK 2.0 工具定義 ──
def search_finance_rss(keyword: str) -> str:
    """在各大財經 RSS 來源中檢索新聞（內建實體提煉與中英文同義詞擴展）。

    Args:
        keyword: 檢索標的名稱或關鍵字
    """
    logger.info(f"🛠️ [Tool] 執行 search_finance_rss: '{keyword}'")
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
    logger.info(f"🛠️ [Tool] 執行 fetch_latest_market_overview (區域: {focus_region})")
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

# ── 3. 系統指示詞 ──
SYSTEM_INSTRUCTION = """你是一位資深的避險基金分析師與全球半導體/科技投資總監。
你的職責是自主調用工具獲取客觀真實的財經資訊，並以繁體中文撰寫深度專業分析。

排版規範：
1. 嚴禁使用 Markdown 標題符號（嚴禁出現 #, ##, ###）。
2. 標題請一律使用 emoji 搭配單星號粗體，例如：*【核心結論】*。
3. 粗體一律使用單星號：*重點文字*。
4. 連結格式：[新聞中文標題](新聞網址)。
"""

# ── 4. 供 ADK CLI / Web 辨識的 Agent 物件 ──
# CLOUD_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
# LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "gemma4:12b")
# 
# # ADK CLI / Web 載入時會自動認證並綁定此 root_agent
# root_agent = Agent(
#     name="finance_director_agent",
#     model=CLOUD_MODEL_NAME,
#     instruction=SYSTEM_INSTRUCTION,
#     tools=AVAILABLE_TOOLS
# )
# agent = root_agent  # 增加別名相容性


# ── 4. 供 ADK CLI / Web 辨識的 Agent 物件（依 RUN_MODE 動態構建） ──
RUN_MODE = os.getenv("RUN_MODE", "cloud").lower()

CLOUD_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "gemma4:12b")
OPENWEBUI_BASE_URL = os.getenv("OPENWEBUI_BASE_URL", "http://172.10.0.22:8080/api")
OPENWEBUI_API_KEY = os.getenv("OPENWEBUI_API_KEY", "sk-abc")

if RUN_MODE == "local":
    logger.info(f"⚙️ [Agent] 正在配置地端模式 (OpenWebUI: {LOCAL_MODEL_NAME})")
    
    # 同時設置這兩組，讓 litellm 與 openai 客戶端都能抓到自訂 Base URL
    os.environ["OPENAI_API_BASE"] = OPENWEBUI_BASE_URL
    os.environ["OPENAI_BASE_URL"] = OPENWEBUI_BASE_URL
    os.environ["OPENAI_API_KEY"] = OPENWEBUI_API_KEY
    
    # 格式：openai/<你的模型名稱>
    active_agent_model = f"openai/{LOCAL_MODEL_NAME}"
else:
    logger.info(f"☁️ [Agent] 正在配置雲端模式 (Gemini: {CLOUD_MODEL_NAME})")
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        os.environ["GEMINI_API_KEY"] = gemini_key
    active_agent_model = CLOUD_MODEL_NAME

# 註冊頂層 root_agent
root_agent = Agent(
    name="finance_director_agent",
    model=active_agent_model,
    instruction=SYSTEM_INSTRUCTION,
    tools=AVAILABLE_TOOLS
)
agent = root_agent


# ── 5. 提供給外部程式（如 Telegram）統一調用的推論函式 ──
def clean_markdown_headings(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            lines.append(f"\n*{stripped.lstrip('#').strip()}*")
        else:
            lines.append(line)
    return "\n".join(lines)

def run_agent_query(prompt: str, mode: str = "cloud") -> str:
    """供 Telegram Bot 呼叫的統一入口"""
    if mode == "cloud":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "❌ 缺少 GEMINI_API_KEY"
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=CLOUD_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=AVAILABLE_TOOLS,
                temperature=0.2
            )
        )
        return clean_markdown_headings(response.text or "")
    else:
        # 地端 OpenWebUI (OpenAI 格式調用)
        base_url = os.getenv("OPENWEBUI_BASE_URL", "http://172.10.0.22:8080/api")
        api_key = os.getenv("OPENWEBUI_API_KEY", "sk-abc")
        client = OpenAI(base_url=base_url, api_key=api_key)

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

        response = client.chat.completions.create(
            model=LOCAL_MODEL_NAME,
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
                obs = fn(**args) if fn else "未定義之工具"
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": str(obs)
                })

            final_res = client.chat.completions.create(
                model=LOCAL_MODEL_NAME,
                messages=messages,
                temperature=0.2
            )
            return clean_markdown_headings(final_res.choices[0].message.content or "")

        return clean_markdown_headings(choice.content or "")