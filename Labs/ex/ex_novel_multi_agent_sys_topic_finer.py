import requests
import json
import re
import sys
import argparse

# python lab_1_5_multi_agent_sys_topic_finer.py "太空中的最後一杯咖啡" --turns 5

# 1. 設定 API 參數
OLLAMA_API_URL = "http://172.10.0.2:8080/api/chat/completions"
#OLLAMA_API_URL = "http://localhost:8080/api/chat/completions"

# /api/v1,/api/chat/completions

OPENWEBUI_API_KEY = "sk-f60ffbf03ede457987a23650b8b11763" 

#MODEL_WORKER = "gemma4_e4b_ctx_2048:latest"
#MODEL_AUDIENCE = "gemma4_e4b_ctx_2048:latest"
MODEL_WORKER = "gemma4_e4b_nothink:latest"
MODEL_AUDIENCE = "gemma4_e4b_nothink:latest"

def get_api_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENWEBUI_API_KEY}"
    }

# 2. 定義系統提示詞
WRITER_PROMPT = (
    "你是一位專業的故事作家。請根據使用者的主題寫出一篇極短篇小說（100-200字）。"
    "你會收到目前為止「歷史評分最高」的故事版本以及編輯的建議。請在這個最佳版本的基礎上，"
    "進行結構或文字的微調優化，使其更臻完美。不要完全重寫與原本無關的故事。"
)

EDITOR_PROMPT = (
    "你是一位嚴格的文學編輯。請閱讀目前歷史最佳的故事與觀眾反饋，並給出1到2句具體、一針見血的修改建議，"
    "特別專注在如何加強起承轉合與故事賣點。"
)

AUDIENCE_PROMPT = (
    "你是一位挑剔的小說讀者。請針對作家最新版的故事進行嚴格評分（給出1-10分）。"
    "你必須嚴格按照以下格式回覆，不要包含任何額外的廢話、聊天或解釋：\n"
    "1. 故事完整及張力: [分數]\n"
    "2. 有足夠的起承轉合: [分數]\n"
    "3. 有賣點: [分數]\n"
    "4. 文句流暢易懂: [分數]\n"
    "原因: [簡短的一句評語]"
)

def call_llm(messages, model_name):
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.3,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_API_URL, headers=get_api_headers(), json=payload, timeout=240)
        response.raise_for_status()
        result = response.json()
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content'].strip()
        elif 'message' in result:
            return result['message']['content'].strip()
        else:
            raise KeyError("找不到 content 欄位")
    except requests.exceptions.RequestException as e:
        print(f"\n❌ API 呼叫失敗！錯誤訊息: {e}")
        raise e

def parse_audience_scores(text):
    scores = re.findall(r'\d\.\s*[^:]+:\s*([0-9.]+)', text)
    if len(scores) == 4:
        try:
            return [float(s) for s in scores]
        except ValueError:
            return [0.0, 0.0, 0.0, 0.0]
    return [0.0, 0.0, 0.0, 0.0]

def run_multi_agent_system(topic: str, max_turns: int = 7):
    print(f"🎬 任務開始！主題：【{topic}】")
    print(f"🚨 安全天花板上限：{max_turns} 輪")
    print("🧠 啟用機制：歷史最佳結果記憶錨定 + 終極回溯選擇機制\n" + "="*60)
    
    # --- 💡 核心記憶體宣告 ---
    best_story = ""
    best_score = -1.0
    best_turn = 0
    best_review = ""
    
    # 初始化 Worker 記憶歷史
    writer_messages = [{"role": "system", "content": WRITER_PROMPT}]
    editor_messages = [{"role": "system", "content": EDITOR_PROMPT}]
    
    # 第一輪的初始引導
    current_message = f"請寫一個關於「{topic}」的故事。"
    
    for turn in range(1, max_turns + 1):
        print(f"\n🔄 =======【 第 {turn} / {max_turns} 輪 協作修訂 】=======")
        
        # 1. 作家寫作（在上一輪輸入的引導下創作）
        writer_messages.append({"role": "user", "content": current_message})
        latest_story = call_llm(writer_messages, MODEL_WORKER)
        writer_messages.append({"role": "assistant", "content": latest_story})
        print(f"✍️ 【作家 Agent】:\n{latest_story}\n" + "-" * 30)
        
        # 2. 觀眾評分
        audience_messages = [
            {"role": "system", "content": AUDIENCE_PROMPT},
            {"role": "user", "content": f"請評估這個故事：\n{latest_story}"}
        ]
        audience_review = call_llm(audience_messages, MODEL_AUDIENCE)
        print(f"👀 【觀眾 Agent 評分結果】:\n{audience_review}")
        
        scores = parse_audience_scores(audience_review)
        avg_score = sum(scores) / 4 if scores else 0
        print(f"📊 當前版本平均分：{avg_score:.2f} / 10")
        
        # --- 💡 記憶體更新邏輯 ---
        if avg_score > best_score:
            best_score = avg_score
            best_story = latest_story
            best_turn = turn
            best_review = audience_review
            print(f"✨ 【系統公告】偵測到更優秀的作品！已更新「歷史最佳記憶」（第 {best_turn} 輪，分數: {best_score:.2f}）")
        else:
            print(f"ℹ️ 【系統公告】此輪表現未超越歷史最佳（{best_score:.2f}），保留原記憶。")
            
        # 3. 檢查是否達到滿意門檻
        if avg_score >= 8.5:
            print(f"\n🎉 【系統】太棒了！第 {turn} 輪作品達到 8.5 門檻，任務圓滿結束！")
            best_story = latest_story # 當前即最佳
            best_score = avg_score
            best_turn = turn
            break
            
        # 4. 未達門檻，交給編輯 Agent 給予修改建議
        editor_input = (
            f"目前歷史最高分的故事是（第 {best_turn} 輪，分數 {best_score:.2f}）：\n{best_story}\n\n"
            f"觀眾對該最高分版本的最新評語是：\n{best_review}\n\n"
            f"請給出進一步的優化具體建議。"
        )
        editor_messages.append({"role": "user", "content": editor_input})
        editor_advice = call_llm(editor_messages, MODEL_WORKER)
        editor_messages.append({"role": "assistant", "content": editor_advice})
        print(f"-" * 30 + f"\n🧐 【編輯 Agent 修改意見】:\n{editor_advice}")
        
        # --- 💡 記憶反饋 ---
        current_message = (
            f"請以此「歷史最佳版本」為基礎進行修改：\n{best_story}\n\n"
            f"修改參考建議：'{editor_advice}'。請微調優化它，目標是衝破 8.5 分！"
        )
        
    else:
        print(f"\n⚠️ 【系統】已達到天花板上限 {max_turns} 輪，未能在過程中突破 8.5 分門檻。")

    # --- 🏆 終極回溯選擇機制輸出 ---
    print("\n" + "="*25 + " 🏆 最終精選結果 " + "="*25)
    print(f"選出輪次：第 {best_turn} / {max_turns} 輪")
    print(f"最終評分：{best_score:.2f} / 10 分")
    print(f"📝 獲選故事成品：\n{best_story}")
    print("="*66)

if __name__ == "__main__":
    # 建立參數解析器
    parser = argparse.ArgumentParser(description="Multi-Agent 故事協作修訂系統")
    
    # 增加必填的位置參數 (topic)
    parser.add_argument("topic", type=str, help="小說創作的指定主題")
    
    # 順便增加一個可選參數 (--turns)，方便你隨時在終端機調整上限輪數（預設為 15 輪）
    parser.add_argument("--turns", type=int, default=15, help="協作修改的最大輪次上限 (預設: 15)")
    
    # 解析終端機輸入的參數
    args = parser.parse_args()
    
    # 執行主程式，帶入終端機解析出的參數
    run_multi_agent_system(topic=args.topic, max_turns=args.turns)
