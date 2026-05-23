"""Review workflow graph — LangGraph state machine for SM-2 review scheduling.

This graph is the spaced-repetition side of the backend. Read it after
`states.py` and the interview graphs so you can see how mastery and review
scheduling are derived from learning performance.

Flow: LoadQuestion -> Evaluate -> ScheduleReview -> Persist

Based on 04_LangGraph_Workflow.md — simplified SM-2 review scheduling.
"""

import logging
from datetime import datetime, timedelta
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.graphs.states import InterviewState

logger = logging.getLogger(__name__)

# SM-2 simplified constants
WRONG_THRESHOLD = 3
INITIAL_INTERVAL_DAYS = 1


async def load_question_node(state: dict) -> dict:
    """加载复习所需的题目上下文。

    这个节点的职责是：
    - 确认当前复习对象是否存在
    - 读取题目 ID 或题目文本
    - 为后续复习评价节点准备基础状态

    当前版本还比较轻量，后续可以扩展为：
    - 直接从数据库加载题目详情
    - 加载上一次复习记录
    - 加载学习画像信息
    """
    question_id = state.get("question_id", "")
    question_text = state.get("question_text", "")

    if not question_id and not question_text:
        return {"error_message": "No question provided for review", "next_action": "error"}

    return {
        "next_action": "evaluate",
        "run_id": str(uuid4()),
    }


async def review_evaluator_node(state: dict) -> dict:
    """根据质量评分评估这次复习结果。

    这里使用的是简化版 SM-2 思路：
    - 质量分高，复习间隔延长
    - 质量分低，复习间隔重置

    输入：
    - user_score / quality：用户自评或系统评分
    - mastery_level：当前掌握度
    - metadata：保存间隔天数等中间信息

    输出：
    - mastery_level：更新后的掌握度
    - review_needed：是否需要继续复习
    - _next_review_at：下一次复习时间
    - _review_result：本次复习结果标签
    """
    quality = state.get("user_score", 0)  # Reuse user_score as quality 0-5 scale
    if quality > 5:
        quality = min(5, quality // 20)  # Map 0-100 to 0-5

    metadata = state.get("metadata", {})
    last_interval = metadata.get("interval_days", INITIAL_INTERVAL_DAYS)

    if quality >= WRONG_THRESHOLD:
        # Correct — double interval
        interval = last_interval * 2
        review_result = "correct"
        mastery_delta = 1
    else:
        # Wrong — reset
        interval = INITIAL_INTERVAL_DAYS
        review_result = "wrong"
        mastery_delta = -1

    next_review = datetime.utcnow() + timedelta(days=interval)
    metadata["interval_days"] = interval
    metadata["review_quality"] = quality

    # Update mastery
    current_mastery = state.get("mastery_level", 1)
    new_mastery = max(1, min(5, current_mastery + mastery_delta))

    return {
        "mastery_level": new_mastery,
        "review_needed": quality < WRONG_THRESHOLD,
        "metadata": metadata,
        "next_action": "schedule",
        "_next_review_at": next_review.isoformat(),
        "_review_result": review_result,
    }


async def schedule_review_node(state: dict) -> dict:
    """计算并设置下一次复习时间。

    这个节点的作用是把评价结果翻译成“什么时候再练”的具体时间。
    它并不负责真正写数据库，而是把要持久化的信息整理好。
    """
    next_review_str = state.get("_next_review_at", "")
    review_result = state.get("_review_result", "unknown")

    try:
        next_review = datetime.fromisoformat(next_review_str) if next_review_str else None
    except ValueError:
        next_review = datetime.utcnow() + timedelta(days=INITIAL_INTERVAL_DAYS)

    return {
        "next_action": "save",
        "review_cycle": state.get("metadata", {}).get("interval_days", INITIAL_INTERVAL_DAYS),
        "persist_flag": True,
    }


async def review_persister_node(state: dict) -> dict:
    """标记复习结果，交给服务层执行真正的持久化。

    这里仍然遵守同一个原则：
    - node 负责流程状态
    - service / repository 负责真正的数据库写入
    """
    return {
        "persist_flag": True,
        "next_action": "save",
        "state_version": "1.0",
    }


def build_review_graph() -> StateGraph:
    """Build and compile the review scheduling graph."""
    workflow = StateGraph(InterviewState)

    # Add nodes
    workflow.add_node("load_question", load_question_node)
    workflow.add_node("evaluator", review_evaluator_node)
    workflow.add_node("schedule", schedule_review_node)
    workflow.add_node("persister", review_persister_node)

    # Edges
    workflow.add_edge(START, "load_question")
    workflow.add_edge("load_question", "evaluator")
    workflow.add_edge("evaluator", "schedule")
    workflow.add_edge("schedule", "persister")
    workflow.add_edge("persister", END)

    return workflow.compile()


# Compiled graph instance
review_graph = build_review_graph()
