"""Explanation workflow graph — LangGraph state machine.

This is the simplest linear workflow in the backend and is a good entry point
for understanding how the agent graph is assembled.

Reading order tip:
- Read `states.py` first.
- Then read this file to see a simple linear graph.
- Then compare with `interview_graph.py` to see routing/branching.

Flow: Extractor -> Classifier -> Explainer -> Persister

Based on 04_LangGraph_Workflow.md phase 1 linear链路.
"""

from langgraph.graph import END, START, StateGraph

from app.graphs.states import InterviewState
from app.graphs.nodes.interview_nodes import (
    extractor_node,
    classifier_node,
    explainer_node,
    persister_node,
)


def build_explanation_graph() -> StateGraph:
    """构建并编译讲解工作流图。

    这是一个最简化的线性图，适合作为理解 LangGraph 结构的起点：
    输入 -> 分类 -> 讲解 -> 持久化

    它不承担复杂分支控制，只负责把最基础的讲解闭环串起来。
    """
    workflow = StateGraph(InterviewState)

    # Add nodes
    workflow.add_node("extractor", extractor_node)
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("explainer", explainer_node)
    workflow.add_node("persister", persister_node)

    # Linear edges
    workflow.add_edge(START, "extractor")
    workflow.add_edge("extractor", "classifier")
    workflow.add_edge("classifier", "explainer")
    workflow.add_edge("explainer", "persister")
    workflow.add_edge("persister", END)

    return workflow.compile()


# Compiled graph instance
explanation_graph = build_explanation_graph()
