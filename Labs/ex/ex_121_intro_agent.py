import re

# 1. 定義 Agent 可以使用的「工具」
def calculate(expression: str) -> str:
    """這是一個外部工具：計算機，負責精準計算數學題"""
    try:
        # 安全地執行數學運算
        allowed_chars = "0123456789+-*/(). "
        if all(c in allowed_chars for c in expression):
            return str(eval(expression))
        return "錯誤：包含非法字元"
    except Exception as e:
        return f"計算出錯: {str(e)}"

# 2. 模擬 LLM 的「大腦」
# 這裡我們用一個簡單的函數來模擬 LLM 接收到問題後的「思考與決策」
def simulate_llm_response(user_question: str, history: str = "") -> str:
    # 模擬場景 1：剛收到問題，LLM 發現自己不會算，決定呼叫工具
    if "Action:" not in history:
        return (
            "Thought: 這個數學問題太複雜了，我直接心算可能會出錯。我應該使用計算機工具來獲得精準答案。\n"
            "Action: calculate((234 * 456) + 789)"
        )
    
    # 模擬場景 2：工具執行完了，LLM 看到結果，做最後的總結
    else:
        # 從歷史紀錄中找出工具的執行結果 (Observation)
        match = re.search(r"Observation: (\d+)", history)
        result = match.group(1) if match else "未知"
        return (
            f"Thought: 我已經透過計算機工具得到了正確答案是 {result}。\n"
            f"Final Answer: 經過精準計算，(234 * 456) + 789 的答案是 {result}。"
        )

# 3. Agent 核心工作流 (The Agent Loop)
def run_agent(question: str):
    print(f"🤖 用戶提問: {question}\n")
    
    # 初始化記憶（歷史紀錄）
    agent_memory = ""
    
    # 進入 Agent 的核心循環（最多嘗試 3 次，防止死循環）
    for step in range(1, 4):
        print(f"--- 🔄 步驟 {step} ---")
        
        # 🧠 思考：LLM 決定下一步要做什麼
        llm_output = simulate_llm_response(question, agent_memory)
        print(llm_output)
        
        # 將 LLM 的思考和決定記錄下來
        agent_memory += llm_output + "\n"
        
        # 🎯 檢查：LLM 是否已經給出最終答案？
        if "Final Answer:" in llm_output:
            print("\n✅ Agent 任務完成！")
            break
            
        # 🛠️ 執行行動：如果 LLM 要求呼叫工具
        if "Action:" in llm_output:
            # 提取工具名稱和參數
            action_line = [line for line in llm_output.split("\n") if "Action:" in line][0]
            # 提取括號內的表達式
            expr = re.search(r"\((.*)\)", action_line).group(1)
            
            print(f"⚙️ [系統自動化] 正在呼叫工具 calculate，參數: {expr}")
            
            # 執行工具並取得觀測結果
            observation = calculate(expr)
            print(f"👀 觀測結果 (Observation): {observation}")
            
            # 將工具的結果餵回給 Agent 的記憶
            agent_memory += f"Observation: {observation}\n"

# 執行 Agent
run_agent("請幫我計算 (234 * 456) + 789 是多少？")
