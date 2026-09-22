#
# python app.py [西元生日年月日]
# python app.py 19880501
#
import sys
import json

from llm_client import create_client
from tools import tools
from fate_tool import calculate_fate_weight


def main():

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            "python app.py 19880501"
        )

        return

    birthday = sys.argv[1]

    client = create_client()

    user_prompt = (
        f"我的生日是 {birthday}，"
        "請幫我計算今天的命重。"
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

    if not msg.tool_calls:

        print("模型沒有呼叫工具")
        print(msg.content)
        return

    tool_call = msg.tool_calls[0]
    
    args = json.loads(
        tool_call.function.arguments
    )

    result = calculate_fate_weight(
        args["date_of_birth"]
    )

    followup = client.chat.completions.create(
        model="gemma4_e4b_ctx_2048:latest",
        messages=[
            {
                "role": "user",
                "content": user_prompt
            },
            msg,
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(
                    result,
                    ensure_ascii=False
                )
            }
        ]
    )

    print("\n====================")
    print(followup.choices[0].message.content)
    print("====================")


if __name__ == "__main__":
    main()