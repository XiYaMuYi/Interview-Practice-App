"""LangGraph nodes for the interview workflow.

Each node is a pure function that reads/writes the InterviewState dict.
Nodes delegate to services for LLM calls and DB access — they don't directly
call providers or write SQL.
"""

import json
import logging
from datetime import datetime
from uuid import uuid4

from app.graphs.states import InterviewState
from app.infra.llm.gateway import llm_gateway

logger = logging.getLogger(__name__)


async def extractor_node(state: InterviewState) -> dict:
    """Extract questions from raw input text.

    Reads input_text, outputs question_text and parsed_content.
    """
    input_text = state.get("input_text", "")
    if not input_text.strip():
        return {"error_message": "Empty input", "next_action": "error"}

    # Try to extract question structure via LLM
    prompt = (
        "你是一个面试题提取器。请从以下文本中提取出题目的核心内容。\n"
        "如果文本是一个明确的问题，直接返回问题内容。\n"
        "如果包含多个问题，提取第一个。\n\n"
        "输出JSON格式：\n"
        "- question_text: 识别出的题目文本\n"
        "- is_note: 是否是笔记而不是题目（true/false）\n\n"
        f"源文本：{input_text[:3000]}"
    )

    try:
        result = await llm_gateway.chat_json(
            [{"role": "system", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        return {
            "question_text": result.get("question_text", input_text),
            "parsed_content": result,
            "next_action": "classify",
            "run_id": str(uuid4()),
        }
    except Exception as e:
        logger.warning(f"Extractor node failed: {e}")
        return {
            "question_text": input_text,
            "parsed_content": {"raw": input_text},
            "next_action": "classify",
            "error_message": str(e),
        }


async def classifier_node(state: InterviewState) -> dict:
    """Classify the extracted question: type, domain, difficulty, tags.

    Reads question_text, outputs question_type, domain_type, difficulty_level, tags, knowledge_points, prerequisites.
    """
    question_text = state.get("question_text", "")

    prompt = (
        "你是一个技术面试分类专家。请对以下问题进行分类。\n\n"
        f"问题：{question_text}\n\n"
        "输出JSON格式：\n"
        "- question_type: concept/compare/scenario/architecture/project/followup\n"
        "- domain_type: RAG/Agent/LangGraph/Prompting/VectorDB/Deployment/Evaluation/General\n"
        "- difficulty_level: 1-5整数\n"
        "- tags: 字符串数组，最多5个\n"
        "- knowledge_points: 知识点字符串数组\n"
        "- prerequisites: 前置知识字符串数组\n"
    )

    try:
        result = await llm_gateway.chat_json(
            [{"role": "system", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        return {
            "question_type": result.get("question_type", "concept"),
            "domain_type": result.get("domain_type", "General"),
            "difficulty_level": result.get("difficulty_level", 3),
            "tags": result.get("tags", []),
            "knowledge_points": result.get("knowledge_points", []),
            "prerequisites": result.get("prerequisites", []),
            "next_action": "retrieve",
        }
    except Exception as e:
        logger.warning(f"Classifier node failed: {e}")
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

    For MVP, this is a placeholder — real retrieval needs embeddings.
    """
    question_text = state.get("question_text", "")
    tags = state.get("tags", [])

    # MVP: return empty hits (will route to explainer)
    # In production, search pgvector by embedding
    return {
        "retrieval_hits": [],
        "next_action": "interview",
    }


async def explainer_node(state: InterviewState) -> dict:
    """Generate layered explanation for a question.

    Outputs answer_short, answer_detail, explanation.
    """
    question_text = state.get("question_text", "")
    knowledge_points = state.get("knowledge_points", [])

    context = ""
    if knowledge_points:
        context = f"\n相关知识点：{', '.join(knowledge_points)}"

    prompt = (
        "你是一个技术面试讲解专家。请对以下问题进行分层讲解。\n\n"
        f"问题：{question_text}{context}\n\n"
        "输出JSON格式：\n"
        "- answer_short: 一句话核心答案\n"
        "- answer_detail: 面试版回答（适合在1-2分钟内说）\n"
        "- explanation: 深入讲解，包括技术细节和易错点\n"
        "- common_pitfalls: 常见易错点\n"
    )

    try:
        result = await llm_gateway.chat_json(
            [{"role": "system", "content": prompt}],
            temperature=0.5,
            max_tokens=2000,
        )
        return {
            "answer_short": result.get("answer_short", ""),
            "answer_detail": result.get("answer_detail", ""),
            "explanation": result.get("explanation", ""),
            "common_pitfalls": result.get("common_pitfalls", ""),
            "next_action": "save",
        }
    except Exception as e:
        logger.warning(f"Explainer node failed: {e}")
        return {
            "error_message": str(e),
            "next_action": "save",
        }


async def interviewer_node(state: InterviewState) -> dict:
    """Act as an interviewer: ask a question or follow-up.

    Reads question context and user's previous answer, outputs followup_questions.
    """
    question_text = state.get("question_text", "")
    user_answer = state.get("user_answer", "")
    difficulty = state.get("difficulty_level", 3)
    chat_history = state.get("chat_history", [])

    metadata = state.get("metadata", {})
    current_turns = metadata.get("followup_turns", 0)
    metadata["followup_turns"] = current_turns + 1

    # Build conversation context
    history_str = ""
    for msg in chat_history[-6:]:
        history_str += f"{msg['role']}: {msg['content']}\n"

    prompt = (
        "你是一个严格的技术面试官。根据以下信息生成追问。\n\n"
        f"原问题：{question_text}\n"
        f"用户回答：{user_answer}\n"
        f"难度等级：{difficulty}\n"
        f"当前追问轮次：{current_turns + 1}\n"
        f"对话历史：\n{history_str}\n\n"
        "输出JSON格式：\n"
        "- followup_questions: 1-2个追问问题\n"
        "- evaluation: 对用户回答的简短评价\n"
    )

    try:
        result = await llm_gateway.chat_json(
            [{"role": "system", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )
        return {
            "followup_questions": result.get("followup_questions", []),
            "chat_history": chat_history + [
                {"role": "user", "content": user_answer},
                {"role": "assistant", "content": result.get("evaluation", "")},
            ],
            "metadata": metadata,
            "next_action": "evaluate",
        }
    except Exception as e:
        logger.warning(f"Interviewer node failed: {e}")
        return {
            "followup_questions": [],
            "error_message": str(e),
        }


async def evaluator_node(state: InterviewState) -> dict:
    """Evaluate the user's answer against the question.

    Outputs user_score, evaluation, feedback, mastery_level, review_needed.
    """
    question_text = state.get("question_text", "")
    user_answer = state.get("user_answer", "")
    answer_detail = state.get("answer_detail", "")

    reference = answer_detail or f"请基于题目自行判断：\n{question_text}"

    prompt = (
        "你是一个技术面试评分专家。请评估以下用户回答。\n\n"
        f"问题：{question_text}\n"
        f"参考答案：{reference}\n"
        f"用户回答：{user_answer}\n\n"
        "输出JSON格式：\n"
        "- score: 0-100的整数\n"
        "- feedback: 简短反馈\n"
        "- missing_points: 遗漏的关键点数组\n"
        "- is_pass: true/false (>=60为pass)\n"
        "- review_needed: 是否需要复习 (true/false)\n"
    )

    try:
        result = await llm_gateway.chat_json(
            [{"role": "system", "content": prompt}],
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

        return {
            "user_score": score,
            "evaluation": result,
            "feedback": result.get("feedback", ""),
            "mastery_level": mastery,
            "review_needed": result.get("review_needed", score < 60),
            "next_action": "save",
        }
    except Exception as e:
        logger.warning(f"Evaluator node failed: {e}")
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
