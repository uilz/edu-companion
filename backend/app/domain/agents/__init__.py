"""Agent 体系 — 教学助手（单 Agent）

设计简化：不再区分 tutor/coach/secretary/orchestrator，
教学助手是唯一的对话切入点，通过 LLM tool calling 自主完成所有工作。
"""

# 保留模块存在即可，所有逻辑在 reply_pipeline.py
