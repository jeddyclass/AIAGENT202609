# app/__init__.py
from .agent import root_agent

# 讓 ADK CLI 能夠直接抓到 agent 變數
agent = root_agent

