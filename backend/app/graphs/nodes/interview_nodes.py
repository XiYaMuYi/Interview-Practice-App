"""LangGraph nodes for the interview workflow.

Each node is a pure function that reads/writes the InterviewState dict.
Nodes delegate to PromptRegistry + LLMGateway for prompts and model calls —
no hardcoded prompts in node bodies.

Cache keys include node name + prompt_version for explicit cache invalidation.
"""

import hashlib
import json
import logging
from uuid import uuid4

from app.graphs.states import InterviewState
from app.infra.cache.cache_service import TTL_QUESTION, get_cache, set_cache
from app.infra.llm.gateway import llm_gateway, prompt_registry

logger = logging.getLogger(__name__)

def _resolve_node_prompt_versions() -> dict[str, str]:
    """Build node -> prompt_version mapping from the registry.

    This ensures cache keys stay in sync with actual prompt versions.
    Falls back to hardcoded defaults if a template is missing.
    """
    defaults = {
        "extractor": "question_extraction_raw",
        "classifier": "question_classification",
        "explainer": "question_explanation",
        "interviewer": "interview_followup",
        "evaluator": "interview_evaluation",
    }
    versions = {}
    for node, prompt_key in defaults.items():
        tpl = prompt_registry.get_template(prompt_key)
        versions[node] = tpl.version if tpl else "unknown"
    return versions

# Prompt version for each node's registered prompt — derived from registry.
_NODE_PROMPT_VERSIONS = _resolve_node_prompt_versions()


async def _node_cache_get(node_name: str, variables: dict) -> tuple[dict | None, str]:
    """Check node-level cache keyed by node + prompt_version + variable hash.

    Always returns (cached_value_or_None, cache_key) for consistent unpacking.
    """
    prompt_ver = _NODE_PROMPT_VERSIONS.get(node_name, "unknown")
    var_hash = hashlib.sha256(
        "|".join(f"{k}={v}" for k, v in sorted(variables.items())).encode()
    ).hexdigest()[:16]
    key = f"app:graph:node:{node_name}:{prompt_ver}:{var_hash}"
    raw = await get_cache(key)
    if raw is not None:
        logger.info(f"Node cache HIT: {key}")
        return (raw if isinstance(raw, dict) else None), key
    return None, key


async def _node_cache_set(key: str, value: dict) -> None:
    """Store node result in cache with TTL."""
    try:
        await set_cache(key, value, ttl=TTL_QUESTION)
    except Exception:
        pass


async def _emit_node_event(node_name: str, prompt_key: str, status: str, detail: str = "") -> None:
    """Publish a node lifecycle event for observability."""
    try:
        from app.infra.events.event_publisher import event_publisher
        prompt_ver = _NODE_PROMPT_VERSIONS.get(node_name, "unknown")
        await event_publisher.publish(f"graph.node.{status}", {
            "node": node_name,
            "prompt_key": prompt_key,
            "prompt_version": prompt_ver,
            "status": status,
            "detail": detail[:200] if detail else "",
        })
    except Exception:
        pass


async def extractor_node(state: InterviewState) -> dict:
    """Extract questions from raw input text.

    Uses: question_extraction_raw prompt from registry.
    Cached by input_text hash + prompt_version.
    """
    input_text = state.get("input_text", "")
    if not input_text.strip():
        return {"error_message": "Empty input", "next_action": "error"}

    cache_vars = {"text": input_text[:3000]}
    cached, cache_key = await _node_cache_get("extractor", cache_vars)
    if cached is not None:
        return cached

    try:
        result = await llm_gateway.chat_json_with_prompt(
            "question_extraction_raw",
            variables=cache_vars,
            temperature=0.3,
            max_tokens=500,
        )
        output = {
            "question_text": result.get("question_text", input_text),
            "parsed_content": result,
            "next_action": "classify",
            "run_id": str(uuid4()),
        }
        await _node_cache_set(cache_key, output)
        await _emit_node_event("extractor", "question_extraction_raw", "success")
        return output
    except Exception as e:
        logger.warning(f"Extractor node failed: {e}")
        await _emit_node_event("extractor", "question_extraction_raw", "failed", str(e))
        return {
            "question_text": input_text,
            "parsed_content": {"raw": input_text},
            "next_action": "classify",
            "error_message": str(e),
        }


async def classifier_node(state: InterviewState) -> dict:
    """Classify the extracted question: type, domain, difficulty, tags.

    Uses: question_classification prompt from registry.
    Cached by question_text hash + prompt_version.
    """
    question_text = state.get("question_text", "")

    cache_vars = {"text": question_text}
    cached, cache_key = await _node_cache_get("classifier", cache_vars)
    if cached is not None:
        return cached

    try:
        result = await llm_gateway.chat_json_with_prompt(
            "question_classification",
            variables=cache_vars,
            temperature=0.3,
            max_tokens=500,
        )
        output = {
            "question_type": result.get("question_type", "concept"),
            "domain_type": result.get("domain_type", "General"),
            "difficulty_level": result.get("difficulty_level", 3),
            "tags": result.get("tags", []),
            "knowledge_points": result.get("knowledge_points", []),
            "prerequisites": result.get("prerequisites", []),
            "next_action": "retrieve",
        }
        await _node_cache_set(cache_key, output)
        await _emit_node_event("classifier", "question_classification", "success")
        return output
    except Exception as e:
        logger.warning(f"Classifier node failed: {e}")
        await _emit_node_event("classifier", "question_classification", "failed", str(e))
        return {
            "question_type": "concept",
            "domain_type": "General",
            "difficulty_level": 3,
            "tags": [],
            "knowledge_points": [],
            "prerequisites": [],
            "error_message": str(e),
        }


async def retriever_node(state: InterviewState) -> dict:
    """Retrieve similar questions and related knowledge.

    MVP placeholder — returns empty hits so routing falls back to explainer.
    In production, search pgvector by embedding.
    """
    return {
        "retrieval_hits": [],
        "next_action": "interview",
    }


async def explainer_node(state: InterviewState) -> dict:
    """Generate layered explanation for a question.

    Uses: question_explanation prompt from registry.
    Cached by question_text + knowledge_points hash + prompt_version.
    """
    question_text = state.get("question_text", "")
    knowledge_points = state.get("knowledge_points", [])

    context = ""
    if knowledge_points:
        context = f"\n相关知识点：{', '.join(knowledge_points)}"

    cache_vars = {"question_text": question_text, "context": context}
    cached, cache_key = await _node_cache_get("explainer", cache_vars)
    if cached is not None:
        return cached

    try:
        result = await llm_gateway.chat_json_with_prompt(
            "question_explanation",
            variables=cache_vars,
            temperature=0.5,
            max_tokens=2000,
        )
        output = {
            "answer_short": result.get("answer_short", ""),
            "answer_detail": result.get("answer_detail", ""),
            "explanation": result.get("explanation", ""),
            "common_pitfalls": result.get("common_pitfalls", ""),
            "next_action": "save",
        }
        await _node_cache_set(cache_key, output)
        await _emit_node_event("explainer", "question_explanation", "success")
        return output
    except Exception as e:
        logger.warning(f"Explainer node failed: {e}")
        await _emit_node_event("explainer", "question_explanation", "failed", str(e))
        return {
            "error_message": str(e),
            "next_action": "save",
        }


async def interviewer_node(state: InterviewState) -> dict:
    """Act as an interviewer: ask a question or follow-up.

    Uses: interview_followup prompt from registry.
    Cached by question + user_answer + turn hash + prompt_version.
    """
    question_text = state.get("question_text", "")
    user_answer = state.get("user_answer", "")
    difficulty = state.get("difficulty_level", 3)
    chat_history = state.get("chat_history", [])

    metadata = state.get("metadata", {})
    current_turns = metadata.get("followup_turns", 0)
    metadata["followup_turns"] = current_turns + 1

    history_str = ""
    for msg in chat_history[-6:]:
        history_str += f"{msg['role']}: {msg['content']}\n"

    cache_vars = {
        "question_text": question_text,
        "user_answer": user_answer,
        "difficulty": str(difficulty),
        "current_turn": str(current_turns + 1),
        "history": history_str,
    }
    cached, cache_key = await _node_cache_get("interviewer", cache_vars)
    if cached is not None:
        return cached

    try:
        result = await llm_gateway.chat_json_with_prompt(
            "interview_followup",
            variables=cache_vars,
            temperature=0.7,
            max_tokens=500,
        )
        output = {
            "followup_questions": result.get("followup_questions", []),
            "chat_history": chat_history + [
                {"role": "user", "content": user_answer},
                {"role": "assistant", "content": result.get("evaluation", "")},
            ],
            "metadata": metadata,
            "next_action": "evaluate",
        }
        await _node_cache_set(cache_key, output)
        await _emit_node_event("interviewer", "interview_followup", "success")
        return output
    except Exception as e:
        logger.warning(f"Interviewer node failed: {e}")
        await _emit_node_event("interviewer", "interview_followup", "failed", str(e))
        return {
            "followup_questions": [],
            "error_message": str(e),
        }


async def evaluator_node(state: InterviewState) -> dict:
    """Evaluate the user's answer against the question.

    Uses: interview_evaluation prompt from registry.
    Cached by question + user_answer + reference hash + prompt_version.
    """
    question_text = state.get("question_text", "")
    user_answer = state.get("user_answer", "")
    answer_detail = state.get("answer_detail", "")

    reference = answer_detail or f"请基于题目自行判断：\n{question_text}"

    cache_vars = {
        "question_text": question_text,
        "reference_answer": reference,
        "user_answer": user_answer,
    }
    cached, cache_key = await _node_cache_get("evaluator", cache_vars)
    if cached is not None:
        return cached

    try:
        result = await llm_gateway.chat_json_with_prompt(
            "interview_evaluation",
            variables=cache_vars,
            temperature=0.3,
            max_tokens=500,
        )
        score = result.get("score", 50)
        # Derive mastery from score
        if score >= 90:
            mastery = 5
        elif score >= 75:
            mastery = 4
        elif score >= 60:
            mastery = 3
        elif score >= 40:
            mastery = 2
        else:
            mastery = 1

        output = {
            "user_score": score,
            "evaluation": result,
            "feedback": result.get("feedback", ""),
            "mastery_level": mastery,
            "review_needed": result.get("review_needed", score < 60),
            "next_action": "save",
        }
        await _node_cache_set(cache_key, output)
        await _emit_node_event("evaluator", "interview_evaluation", "success")
        return output
    except Exception as e:
        logger.warning(f"Evaluator node failed: {e}")
        await _emit_node_event("evaluator", "interview_evaluation", "failed", str(e))
        return {
            "user_score": 0,
            "evaluation": {},
            "feedback": str(e),
            "mastery_level": 1,
            "review_needed": True,
            "error_message": str(e),
        }


async def persister_node(state: InterviewState) -> dict:
    """Mark the workflow result for persistence.

    The actual DB write is done by the calling service — this node just sets the flag.
    """
    return {
        "persist_flag": True,
        "next_action": "save",
        "state_version": "1.0",
    }
