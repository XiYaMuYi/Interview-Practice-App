"""LangGraph state schemas.

All workflow graphs share InterviewState as the canonical state dict.
Fields are TypedDict keys — every node reads/writes a subset.

Based on 04_LangGraph_Workflow.md §2 State Design.
"""

from typing import Any

from typing_extensions import TypedDict


class InterviewState(TypedDict, total=False):
    """Canonical state for all LangGraph workflows.

    Nodes are expected to return partial updates (only changed keys).
    LangGraph merges them into the running state dict.
    """

    # ── Input ─────────────────────────────────────────────────────
    input_text: str
    input_source: str          # upload / paste / chat / manual
    session_id: str
    user_id: str
    file_id: str
    question_id: str           # persisted UUID once saved
    run_id: str

    # ── Parsing / Understanding ───────────────────────────────────
    parsed_content: dict
    question_text: str
    question_type: str         # concept / compare / scenario / architecture / project / followup
    domain_type: str           # RAG / Agent / LangGraph / Prompting / VectorDB / ...
    difficulty_level: int      # 1-5
    tags: list[str]
    knowledge_points: list[str]
    prerequisites: list[str]
    retrieval_hits: list[dict]

    # ── Generation / Interaction ──────────────────────────────────
    answer_short: str
    answer_detail: str
    explanation: str
    common_pitfalls: str
    followup_questions: list[str]
    chat_history: list[dict]   # [{role, content}, ...]
    user_answer: str
    user_score: int            # 0-100
    feedback: str
    evaluation: dict

    # ── Decision / Control ────────────────────────────────────────
    next_action: str           # classify / retrieve / interview / evaluate / save / error / ask
    review_needed: bool
    mastery_level: int         # 1-5
    persist_flag: bool
    state_version: str
    metadata: dict[str, Any]   # free-form extras (followup_turns, max_turns, etc.)
    error_message: str
