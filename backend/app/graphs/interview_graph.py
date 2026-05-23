"""Interview workflow graph — LangGraph state machine for interview simulation.

Reading order tip:
1. Read `states.py` first to understand the state contract.
2. Read this file second to understand the agent routing logic.
3. Read `nodes/interview_nodes.py` third to understand each step.
4. Then read the service layer and repositories.

Flow:
    Extractor -> Classifier -> Retriever -> Explainer/Interviewer -> Evaluator -> Persister

Iteration limits:
    - DEFAULT_MAX_TURNS: hard cap on total interviewer->evaluator cycles (default 5)
    - max_turns in metadata: per-session override (must be <= DEFAULT_MAX_TURNS)
    - Any route that would cause a re-entry past the limit forces convergence to persister.
"""

from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.graphs.states import InterviewState

# Import node implementations
from app.graphs.nodes.interview_nodes import (
    extractor_node,
    classifier_node,
    retriever_node,
    interviewer_node,
    evaluator_node,
    persister_node,
    explainer_node,
)

# Hard cap on total loop iterations across all re-entry paths.
# Prevents infinite cycles: interviewer<->evaluator, evaluator->explainer->interviewer, etc.
DEFAULT_MAX_TURNS = 5


def _total_turns(state: InterviewState) -> int:
    """Count total interviewer->evaluator cycles consumed so far."""
    return state.get("metadata", {}).get("followup_turns", 0)


def _max_allowed(state: InterviewState) -> int:
    """Resolve max turns: per-session override capped by DEFAULT_MAX_TURNS."""
    configured = state.get("metadata", {}).get("max_turns", DEFAULT_MAX_TURNS)
    return min(configured, DEFAULT_MAX_TURNS)


def route_after_extractor(state: InterviewState) -> Literal["classifier"]:
    """抽取器之后固定进入分类器。

    为什么这么设计：
    - 抽取阶段只负责把原始输入变成可识别的题目文本
    - 分类阶段负责补齐题型、领域、难度、标签等结构化信息
    - 两者职责分离后，后续更容易扩展到"简历驱动出题"或"多题拆分"

    当前状态读取：
    - 这里不依赖额外状态字段，只是一个稳定的默认路由。
    """
    return "classifier"


def route_after_classifier(state: InterviewState) -> Literal["retriever", "explainer"]:
    """分类器之后决定先检索还是先讲解。

    路由逻辑：
    - 如果题目难度较高，先进入讲解器，避免用户一上来就被追问压住
    - 如果前置知识为空，也先讲解，先把基础补齐
    - 其余情况进入检索器，尝试召回相似题和相关知识点

    这个分支的核心目标是：
    让系统在"先理解再练习"和"先检索再补充"之间做一个合理权衡。
    """
    difficulty = state.get("difficulty_level", 0)
    prerequisites = state.get("prerequisites", [])
    if difficulty >= 4 or len(prerequisites) == 0:
        return "explainer"
    return "retriever"


def route_after_retriever(state: InterviewState) -> Literal["interviewer", "explainer"]:
    """检索器之后决定进入面试官还是继续讲解。

    路由逻辑：
    - 如果用户意图明确是练习/面试，就直接进入面试官节点
    - 如果没有检索命中，说明上下文不足，回到讲解器做通用说明
    - 如果已有检索命中，进入面试官节点，利用检索结果推进对话

    这个分支体现了 RAG 的核心思想：
    先找上下文，再决定是讲解还是追问。
    """
    hits = state.get("retrieval_hits", [])
    user_intent = state.get("next_action", "")
    if user_intent == "interview" or user_intent == "practice":
        return "interviewer"
    if not hits:
        return "explainer"
    return "interviewer"


def route_after_interviewer(state: InterviewState) -> Literal["evaluator", "interviewer"]:
    """面试官节点之后决定是否继续追问。

    Safety: if total_turns >= max_allowed, force convergence to evaluator.
    """
    if _total_turns(state) >= _max_allowed(state):
        return "evaluator"
    followups = state.get("followup_questions", [])
    if followups and state.get("user_answer"):
        return "interviewer"
    return "evaluator"


def route_after_evaluator(state: InterviewState) -> Literal["explainer", "persister", "interviewer"]:
    """评价器节点之后决定下一步。

    Safety: if total_turns >= max_allowed, force convergence to persister
    regardless of score. No re-entry to interviewer allowed past the limit.
    """
    if _total_turns(state) >= _max_allowed(state):
        return "persister"
    score = state.get("user_score", 0)
    review_needed = state.get("review_needed", False)
    if score < 60 or review_needed:
        return "explainer"
    if score >= 60 and not review_needed:
        return "persister"
    return "interviewer"


def route_after_explainer(state: InterviewState) -> Literal["persister", "interviewer"]:
    """讲解器节点之后决定是保存结果还是继续进入追问。

    路由逻辑：
    - 如果讲解之后系统判断应该继续练习，就进入面试官节点
    - 否则直接进入持久化节点，把结果写回数据库/学习记录

    这里的作用是把"知识讲解"与"训练闭环"连接起来。
    """
    next_action = state.get("next_action", "save")
    if next_action == "ask" or next_action == "interview":
        return "interviewer"
    return "persister"


def build_interview_graph() -> StateGraph:
    """构建并编译完整的面试工作流图。

    这个函数的职责只有一个：把节点和路由关系串起来。
    它不负责具体业务逻辑，也不负责数据库读写。
    真正的业务细节都在各个 node 以及 service 层里。
    """
    workflow = StateGraph(InterviewState)

    # Add nodes
    workflow.add_node("extractor", extractor_node)
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("interviewer", interviewer_node)
    workflow.add_node("evaluator", evaluator_node)
    workflow.add_node("persister", persister_node)
    workflow.add_node("explainer", explainer_node)

    # Edges
    workflow.add_edge(START, "extractor")
    workflow.add_conditional_edges("extractor", route_after_extractor, ["classifier"])
    workflow.add_conditional_edges("classifier", route_after_classifier, ["retriever", "explainer"])
    workflow.add_conditional_edges("retriever", route_after_retriever, ["interviewer", "explainer"])
    workflow.add_conditional_edges("interviewer", route_after_interviewer, ["evaluator", "interviewer"])
    workflow.add_conditional_edges("evaluator", route_after_evaluator, ["explainer", "persister", "interviewer"])
    workflow.add_conditional_edges("explainer", route_after_explainer, ["persister", "interviewer"])
    workflow.add_edge("persister", END)

    return workflow.compile()


# Compiled graph instance
interview_graph = build_interview_graph()
