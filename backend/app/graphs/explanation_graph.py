"""Explanation workflow graph — LangGraph state machine.

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
    """Build and compile the explanation workflow graph."""
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
