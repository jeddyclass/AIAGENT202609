import time
import threading
from enum import Enum

class AgentState(Enum):
    IDLE = "idle"       # 待機
    ACTIVE = "active"   # 主動

class SimpleAgent:
    def __init__(self, heartbeat_interval=60): # 預設60秒心跳
        self.state = AgentState.IDLE
        self.heartbeat_interval = heartbeat_interval
        self.user_input_queue = []  # 模擬使用者輸入
        self.scheduled_tasks = []   # 排程任務
        self.heartbeat_count = 0
        self.max_heartbeats = 5     # 最多主動心跳3次

    def start(self):
        """啟動Agent的心跳循環 (在背景執行緒)"""
        def _loop():
            while True:
                self._heartbeat()
                time.sleep(self.heartbeat_interval)
        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()
        print(f"Agent started. Heartbeat every {self.heartbeat_interval}s.")

    def _heartbeat(self):
        """每一次心跳的邏輯"""
        print(f"[Heartbeat #{self.heartbeat_count}] State: {self.state.value}")

        # 1. 檢查使用者輸入
        if self.user_input_queue:
            user_msg = self.user_input_queue.pop(0)
            print(f"  -> Processing user input: {user_msg}")
            self.state = AgentState.ACTIVE
            self.heartbeat_count = 0
            self._process_user_input(user_msg)
            return

        # 2. 檢查排程任務
        if self.scheduled_tasks:
            # ... (簡化處理)
            pass

        # 3. 主動行為 (只有在ACTIVE狀態下)
        if self.state == AgentState.ACTIVE:
            if self.heartbeat_count < self.max_heartbeats:
                print(f"  -> Agent is ACTIVE. Proactive check #{self.heartbeat_count+1}")
                # 這裡可以執行主動查詢或詢問使用者
                self._proactive_action()
                self.heartbeat_count += 1
            else:
                print("  -> Max heartbeats reached. Going back to IDLE.")
                self.state = AgentState.IDLE
                self.heartbeat_count = 0

    def _process_user_input(self, msg):
        """處理使用者輸入 (簡化)"""
        print(f"  -> [Processing] {msg}")
        # 這裡會觸發後續的Skill執行

    def _proactive_action(self):
        """主動行為 (例如：回報公車資訊)"""
        print(f"  -> [Proactive] Reporting bus status...")

    def receive_input(self, msg):
        """外部介面：接收使用者輸入"""
        self.user_input_queue.append(msg)
        print(f"User input received: {msg}")

# 使用範例
if __name__ == "__main__":
    agent = SimpleAgent(heartbeat_interval=5) # 為了示範，設為5秒
    agent.start()

    # 模擬使用者提問
    time.sleep(7)
    agent.receive_input("今天天氣如何？")

    # 讓程式跑一段時間觀察
    time.sleep(20)
