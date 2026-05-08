"""Interview workflow graph — LangGraph state machine for interview simulation.

Flow: Extractor -> Classifier -> Retriever -> Interviewer -> Evaluator -> Persister
With conditional edges for looping and branching.

Based on 04_LangGraph_Workflow.md design.
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


def route_after_extractor(state: InterviewState) -> Literal["classifier"]:
    """Extractor always routes to Classifier."""
    return "classifier"


def route_after_classifier(state: InterviewState) -> Literal["retriever", "explainer"]:
    """If difficulty >= 4 or missing prerequisites, go to Explainer first."""
    difficulty = state.get("difficulty_level", 0)
    prerequisites = state.get("prerequisites", [])
    if difficulty >= 4 or len(prerequisites) == 0:
        return "explainer"
    return "retriever"


def route_after_retriever(state: InterviewState) -> Literal["interviewer", "explainer"]:
    """If retrieval hits exist, go to Interviewer; otherwise Explainer."""
    hits = state.get("retrieval_hits", [])
    user_intent = state.get("next_action", "")
    if user_intent == "interview" or user_intent == "practice":
        return "interviewer"
    if not hits:
        return "explainer"
    return "interviewer"


def route_after_interviewer(state: InterviewState) -> Literal["evaluator", "interviewer"]:
    """After user answers, go to Evaluator. If followup needed, loop back to Interviewer."""
    followups = state.get("followup_questions", [])
    if followups and state.get("user_answer"):
        # Check max turns
        metadata = state.get("metadata", {})
        current_turns = metadata.get("followup_turns", 0)
        max_turns = metadata.get("max_turns", 5)
        if current_turns < max_turns:
            return "interviewer"
    return "evaluator"


def route_after_evaluator(state: InterviewState) -> Literal["explainer", "persister", "interviewer"]:
    """Based on score: low -> Explainer, high -> Persister, mid -> Interviewer."""
    score = state.get("user_score", 0)
    review_needed = state.get("review_needed", False)
    if score < 60 or review_needed:
        return "explainer"
    if score >= 60 and not review_needed:
        return "persister"
    return "interviewer"


def route_after_explainer(state: InterviewState) -> Literal["persister", "interviewer"]:
    """After explanation, either persist or go to Interviewer for practice."""
    next_action = state.get("next_action", "save")
    if next_action == "ask" or next_action == "interview":
        return "interviewer"
    return "persister"


def build_interview_graph() -> StateGraph:
    """Build and compile the interview workflow graph."""
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
