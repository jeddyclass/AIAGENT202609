from app.agents import root_agent

def run_interaction():
    session = root_agent.create_session()
    
    # 模擬顧客退款請求
    user_prompt = "我的耳機收到是壞的，訂單是 ORD-10029381，我要退款 250 元。"
    response = session.send_message(user_prompt)
    
    # 當遇到 require_human_confirmation 時，ADK 會暫停並回傳待確認狀態
    if session.is_suspended_for_approval():
        pending_action = session.get_pending_action()
        print(f"\n[ALERT - 人工審核通知]")
        print(f"Agent 嘗試執行敏感操作: {pending_action.tool_name}")
        print(f"參數內容: {pending_action.arguments}")
        
        # 模擬人工審核決策
        approval = input("主管是否同意退款？(y/n): ")
        if approval.lower() == 'y':
            session.approve_action()
            final_response = session.resume()
            print(f"\n[Agent 最終回覆]: {final_response.text}")
        else:
            session.reject_action(reason="未附上損壞照片，拒絕退款")
            final_response = session.resume()
            print(f"\n[Agent 最終回覆]: {final_response.text}")
    else:
        print(response.text)

if __name__ == "__main__":
    run_interaction()
