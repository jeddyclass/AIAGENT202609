# 環境配置與 Ollama 客戶端實作
# 不依賴第三方大模型套件，直接使用標準的 requests 來與 Open-WebUI 終端進行通信。
#
# -[ANS]--------------------------------------------------------------
# SELECT Genre.Name, AVG(Track.Milliseconds) AS AvgDuration
# FROM Track
# JOIN Genre ON Track.GenreId = Genre.GenreId
# GROUP BY Genre.Name
# ORDER BY AvgDuration DESC
# LIMIT 1;
# --------------------------------------------------------------------

import json
import os
import sqlite3
import requests

# 依照要求設定地端引擎參數
# OLLAMA_API_URL = "http://localhost:8080/api/chat/completions"
# OPENWEBUI_API_KEY = "sk-1540f219fcb246b9bb55c7951491c01b" 
# MODEL_WORKER = "gemma4_e4b_ctx_128k_nothink:latest"
# MODEL_AUDIENCE = "gemma4_e2b_nothink:latest"

API_KEY = "sk-f60ffbf03ede457987a23650b8b11763" 
SERVER_URL = "http://172.10.0.2:8080"
ENDPOINT = f"{SERVER_URL}/api/chat/completions"
MODEL_NAME = "gemma4_e4b_ctx_2048:latest"

def call_local_llm(messages: list) -> str:
    """
    呼叫地端 Ollama/Open-WebUI 引擎的共用核心函式
    
    Interface:
    - messages: 符合 OpenAI 格式的對話歷史列表, 例如 [{"role": "user", "content": "..."}]
    - Return: 模型回傳的純文字內容
    """
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.0,  # 設為 0 確保 SQL 生成與推理的穩定性
        "max_tokens": 2048  # 避免文字輸出被腰斬
    }
    
    try:
        response = requests.post(ENDPOINT, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"【LLM 通信錯誤】: {e}"

# 實作純 Python 版本的資料庫工具組 (Tools)
# @tool 裝飾器移除，改寫為純 Python 函式
# Agent 將透過名稱與條件來調用它們。
DB_FILE = "Chinook.db"

def sql_db_list_tables() -> str:
    """工具 1：獲取資料庫中所有可用的資料表名稱。"""
    con = sqlite3.connect(DB_FILE)
    try:
        cursor = con.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
        return ", ".join(tables)
    finally:
        con.close()

def sql_db_schema(table_names: str) -> str:
    """工具 2：傳入以逗號分隔的表名，查詢其 Schema 與前 3 筆範例資料。"""
    con = sqlite3.connect(DB_FILE)
    try:
        cursor = con.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        valid_tables = {row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")}
        results = []
        
        for table in table_names.split(","):
            table = table.strip()
            if table not in valid_tables:
                results.append(f"Error: table_names '{table}' not found in database")
                continue
            
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            schema_row = cursor.fetchone()
            if schema_row:
                results.append(schema_row[0])
                try:
                    quoted_table = f'"{table}"'
                    cursor.execute(f"SELECT * FROM {quoted_table} LIMIT 3;")
                    rows = cursor.fetchall()
                    if rows:
                        col_names = [desc[0] for desc in cursor.description]
                        results.append(
                            f"/*\n3 rows from {table} table:\n"
                            + "\t".join(col_names) + "\n"
                            + "\n".join("\t".join(str(x) for x in row) for row in rows)
                            + "\n*/"
                        )
                except Exception as e:
                    results.append(f"Error fetching sample rows: {e}")
        return "\n\n".join(results)
    finally:
        con.close()

def sql_db_query(query: str) -> str:
    """工具 3：執行 SQL 查詢指令並回傳結果。若發生錯誤則回傳錯誤訊息。"""
    # 簡單防禦 DML 語句
    upper_query = query.upper()
    for forbidden in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER"]:
        if forbidden in upper_query:
            return f"Error: {forbidden} operations are not allowed."
            
    con = sqlite3.connect(DB_FILE)
    try:
        cursor = con.cursor()
        cursor.execute(query)
        res = cursor.fetchall()
        return str(res)
    except Exception as e:
        return f"Error: {e}"
    finally:
        con.close()

def sql_db_query_checker(query: str) -> str:
    """工具 4：在執行 SQL 前，先請 LLM 做語法與邏輯檢查。"""
    prompt = f"""Double check the sqlite query below for common mistakes:
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins

If there are any of the above mistakes, rewrite the query. If there are no mistakes, just reproduce the original query.
Output the final SQL query ONLY. Do not write markdown blocks or any explanations.

SQL Query: {query}"""
    
    return call_local_llm([{"role": "user", "content": prompt}])

# 工具映射字典，便於 Agent 根據名稱動態調用
TOOLS = {
    "sql_db_list_tables": sql_db_list_tables,
    "sql_db_schema": sql_db_schema,
    "sql_db_query": sql_db_query,
    "sql_db_query_checker": sql_db_query_checker
}

# 手動實作 Agent 的 ReAct 思考循環架構
# 不使用 LangChain 的 create_agent
# 改用提示詞工程 (Prompt Engineering) 在地端 LLM 建立一個標準的 ReAct 迴圈
# 模型必須輸出 Action: 工具名稱(參數) 或是最終答案 Final Answer: 您的回答
# 系統提示詞：規範地端 LLM 的思考模式與行為守則
SYSTEM_PROMPT = """You are an agent designed to interact with a SQL database to answer user questions.

You operate in a loop of Thought, Action, and Observation.
At each step, you must output a 'Thought' followed by either an 'Action' or a 'Final Answer'.

Available tools you can use:
1. sql_db_list_tables() -> Returns a comma-separated list of tables. (Takes no arguments)
2. sql_db_schema(table_names) -> Returns schema and samples. (Argument: "table1, table2")
3. sql_db_query(query) -> Executes SQL and returns results. (Argument: "SELECT ...")
4. sql_db_query_checker(query) -> Checks and fixes SQL queries. (Argument: "SELECT ...")

Strict Output Format Rules:
If you need to use a tool, you MUST output exactly in this format:
Thought: [Your reasoning about what to do next]
Action: tool_name(argument)

If you have the final answer for the user, you MUST output exactly in this format:
Thought: [I have found the answer]
Final Answer: [The direct response to the user question]

Behavior Guidelines:
- To start you should ALWAYS look at the tables in the database (sql_db_list_tables) to see what you can query. Do NOT skip this step.
- Then query the schema of the most relevant tables.
- You MUST use sql_db_query_checker to check your query before executing it with sql_db_query.
- Always limit your query to at most 5 results unless specified otherwise.
- DO NOT make any DML statements (INSERT, UPDATE, DELETE).
"""

def parse_action(llm_output: str):
    """
    穩健解析 Action: tool_name(argument)
    支援參數內部包含括號（如 AVG()、COUNT() 或子查詢）
    """
    for line in llm_output.split("\n"):
        if line.strip().startswith("Action:"):
            action_content = line.split("Action:", 1)[1].strip()
            
            # 找到第一個 '(' 與最後一個 ')'
            first_paren = action_content.find("(")
            last_paren = action_content.rfind(")")
            
            if first_paren != -1 and last_paren != -1 and last_paren > first_paren:
                tool_name = action_content[:first_paren].strip()
                tool_arg = action_content[first_paren + 1:last_paren].strip()
                
                # 去除外層可能包裹的引號
                if (tool_arg.startswith('"') and tool_arg.endswith('"')) or \
                   (tool_arg.startswith("'") and tool_arg.endswith("'")):
                    tool_arg = tool_arg[1:-1]
                    
                return tool_name, tool_arg
                
    return None, None
    
def parse_action_bak(llm_output: str):
    """
    解析 LLM 輸出的 Action 語法。
    例如解析 "Action: sql_db_schema(Genre, Track)" 
    -> 傳回 ("sql_db_schema", "Genre, Track")
    """
    if "Action:" in llm_output:
        line = [l for l in llm_output.split("\n") if "Action:" in l][0]
        action_content = line.split("Action:")[1].strip()
        if "(" in action_content and action_content.endswith(")"):
            tool_name = action_content.split("(")[0].strip()
            # 擷取括號內的參數並移除首尾的引號
            tool_arg = action_content.split("(")[1][:-1].strip().strip('"').strip("'")
            return tool_name, tool_arg
    return None, None

def run_db_agent(question: str, max_loops: int = 25):
    """
    主核心介面：驅動 Agent 執行 ReAct 循環直到獲得答案或達最大步數。
    
    Interface:
    - question: 使用者的提問問題
    - max_loops: 思考與行動的最大循環次數，避免死循環
    """
    print(f"🚀 [Agent 開始任務] 詢問問題: {question}\n" + "="*50)
    
    # 初始化對話歷史
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Question: {question}"}
    ]
    
    for i in range(max_loops):
        print(f"\n🔄 [迴圈 第 {i+1} 步]")
        
        # 1. 讓 LLM 進行思考與決定下一步行動
        llm_output = call_local_llm(messages)
        print(f"🤖 LLM 輸出:\n{llm_output}")
        
        # 將 LLM 的思考紀錄加入歷史，保持上下文連貫
        messages.append({"role": "assistant", "content": llm_output})
        
        # 2. 檢查是否產出最終答案
        if "Final Answer:" in llm_output:
            final_answer = llm_output.split("Final Answer:")[1].strip()
            print("\n" + "="*50 + f"\n🎯 [任務成功完成] 最終答案:\n{final_answer}")
            return final_answer
            
        # 3. 解析並執行 Tool
        tool_name, tool_arg = parse_action(llm_output)
        if tool_name in TOOLS:
            print(f"🔧 [執行工具] 調用 {tool_name}，參數: '{tool_arg}'")
            try:
                # 執行對應的在地端 Python 函式
                if tool_name == "sql_db_list_tables":
                    observation = TOOLS[tool_name]()
                else:
                    observation = TOOLS[tool_name](tool_arg)
            except Exception as e:
                observation = f"Tool execution error: {e}"
                
            print(f"👁️ [觀察結果]:\n{observation}")
            # 將工具執行後的結果反饋給 LLM
            messages.append({"role": "user", "content": f"Observation: {observation}"})
        else:
            # 處理 LLM 產出非預期格式的情況
            error_msg = "Observation: Error: Invalid or missing Action format. Please strictly use 'Action: tool_name(argument)' or provide 'Final Answer:'."
            print(f"⚠️ 格式錯誤，要求模型重試")
            messages.append({"role": "user", "content": error_msg})
            
    print("\n❌ [任務失敗]: 已達到最大循環次數，模型未能順利產出 Final Answer。")

# Main function
if __name__ == "__main__":
    # 確保本地已準備好 Chinook.db，如果沒有，請先下載它
    # （下載程式碼與你原本提供的方法相同，此處省略）
    
    # 測試提問
    sample_question = "Which genre on average has the longest tracks?"
    run_db_agent(sample_question)
    