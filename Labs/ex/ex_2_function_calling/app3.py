#
# python app3.py [西元生日年月日] [地點]
# python app3.py 19880501 台北
#
import sys
import json

from llm_client import create_client
from tools import tools
from fate_tool import calculate_fate_weight
from weather_tool import get_weather


def main():

    if len(sys.argv) < 3:
        print(
            "Usage:\n"
            "python app3.py 19880501 台北"
        )
        return

    birthday = sys.argv[1]
    current_loc = sys.argv[2]

    client = create_client()

    # ================== 修改 Prompt ==================
    # 明確告知模型任務：查詢天氣與命重，並綜合兩者判斷「今天適不適合跑步」與「理由」
    user_prompt = (
        f"我現在在 {current_loc}，我的生日是 {birthday}。\n"
        "請幫我查詢今天的天氣和計算我的命重運勢，並幫我評估「今天適不適合去跑步？」\n"
        "請綜合天氣狀況與命重運勢給出具體的理由（例如：就算天氣很好，但如果運勢不佳，也請建議不要去跑步）。"
    )

    response = client.chat.completions.create(
        model="gemma4_e4b_ctx_2048:latest",
        messages=[
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        tools=tools,
        tool_choice="auto"
    )

    msg = response.choices[0].message

    print(f">>> msg: [{msg}]")

    if not msg.tool_calls:
        print("模型沒有呼叫工具")
        print(msg.content)
        return

    # 準備下一階段的對話歷史（必須包含使用者的提問與模型的工具呼叫請求）
    followup_messages = [
        {"role": "user", "content": user_prompt},
        msg # 必須把包含 tool_calls 的 msg 傳回去
    ]

    # 用迴圈處理模型要求的所有工具（包含 get_weather 與 calculate_fate_weight）
    for tool_call in msg.tool_calls:
        tool_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        print(f">>> 正在執行工具: {tool_name}, 參數: {args}")

        # 根據工具名稱分流執行
        if tool_name == "get_weather":
            tool_result = get_weather(args["location"])
        elif tool_name == "calculate_fate_weight":
            tool_result = calculate_fate_weight(args["date_of_birth"])
        else:
            tool_result = {"error": "未知的工具名稱"}

        # 將執行結果加入歷史訊息中（注意：每個結果都必須對應其 tool_call_id）
        followup_messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(tool_result, ensure_ascii=False)
        })
     
    # 第二次呼叫 LLM：讓模型拿到天氣和命重數據後，進行綜合邏輯推理
    followup = client.chat.completions.create(
        model="gemma4_e4b_ctx_2048:latest",
        messages=followup_messages
    )

    print("\n================== 跑步建議 ==================")
    print(followup.choices[0].message.content)
    print("==============================================")


if __name__ == "__main__":
    main()