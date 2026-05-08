"""Review workflow graph — LangGraph state machine for SM-2 review scheduling.

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
    """Load question context for review.

    Reads question_id, outputs question_text and context.
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
    """Evaluate user's review attempt using quality score.

    Reads user_answer, quality (0-5), outputs mastery_level and review_interval.
    SM-2 simplified:
    - quality >= 3 (correct): interval = interval * 2 (initial 1 day)
    - quality < 3 (wrong): interval resets to 1 day
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
    """Calculate and set the next review date."""
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
    """Mark the review result for persistence."""
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
