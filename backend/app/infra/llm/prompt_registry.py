"""Prompt Registry — centralized prompt template management with versioning.

Each prompt has a key, a version, and a system-template string.
Templates use {{{{variable}}}} placeholders for substitution.
"""

from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PromptTemplate:
    key: str
    version: str
    system_template: str
    description: str = ""
    model_hints: dict = field(default_factory=dict)


class PromptRegistry:
    """Central prompt template management with versioning."""

    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}
        self._load_builtin_prompts()

    # ── Public API ──────────────────────────────────────────────────

    def register(self, template: PromptTemplate) -> None:
        self._templates[template.key] = template
        logger.debug(f"Registered prompt template: {template.key} v{template.version}")

    def get_system(self, key: str) -> str | None:
        tpl = self._templates.get(key)
        return tpl.system_template if tpl else None

    def get_template(self, key: str) -> PromptTemplate | None:
        return self._templates.get(key)

    def list_keys(self) -> list[str]:
        return list(self._templates.keys())

    # ── Builtin prompts ─────────────────────────────────────────────

    def _load_builtin_prompts(self) -> None:
        self.register(
            PromptTemplate(
                key="question_extraction",
                version="1.0",
                description="Extract interview-style questions from source text",
                system_template="""你是一个资深技术面试官。请从以下文本中提取出所有面试相关的问题。

要求：
1. 提取所有明确的问题、面试题、追问
2. 对每个问题输出以下 JSON 字段：
   - title: 问题的简短标题（最多50字）
   - content: 问题的完整描述
   - question_type: 从以下选择一个：concept、compare、scenario、architecture、project、followup
   - difficulty_level: 1-5的整数，1最简单，5最难
   - domain_type: 从以下选择一个：RAG、Agent、LangGraph、Prompting、VectorDB、Deployment、Evaluation、General

请以 JSON 数组格式返回，不要包含任何额外说明。每个问题是一个对象。
如果文本中没有可提取的问题，返回空数组 []。

源文本：
{{{text}}}""",
            )
        )

        self.register(
            PromptTemplate(
                key="question_classification",
                version="1.0",
                description="Classify an existing question into type and domain",
                system_template="""你是一个技术面试分类专家。请对以下问题进行分类。

问题标题：{{{title}}}
问题内容：{{{content}}}

请输出以下 JSON 字段：
- question_type: 从以下选择一个：concept、compare、scenario、architecture、project、followup
- domain_type: 从以下选择一个：RAG、Agent、LangGraph、Prompting、VectorDB、Deployment、Evaluation、General
- difficulty_level: 1-5的整数
- difficulty_score: 0.0-1.0的浮点数
- tags: 字符串数组，最多5个技术标签
- summary: 一句话总结该问题考察的核心知识点

请只返回 JSON 对象，不要包含额外说明。""",
            )
        )

        self.register(
            PromptTemplate(
                key="knowledge_node_extraction",
                version="1.0",
                description="Extract knowledge nodes/concepts from text",
                system_template="""你是一个知识图谱构建专家。请从以下文本中提取关键知识节点。

要求：
1. 识别文本中的核心概念、技术术语、先决条件
2. 对每个节点输出以下 JSON 字段：
   - name: 知识节点名称
   - description: 简短描述
   - node_type: 从以下选择一个：concept、prerequisite、topic
   - depth_level: 1-3的整数，1为核心概念，3为细分知识点

请以 JSON 数组格式返回。

源文本：
{{{text}}}""",
            )
        )

        self.register(
            PromptTemplate(
                key="similarity_rerank",
                version="1.0",
                description="Rerank search results by relevance to a query",
                system_template="""你是一个搜索结果排序专家。请根据用户的查询，对以下候选问题进行相关性排序。

用户查询：{{{query}}}

候选问题（JSON 数组）：
{{{candidates}}}

请输出以下 JSON：
- ranked_ids: 按相关性从高到低排列的问题 ID 数组（字符串格式）
- reasoning: 简要说明排序理由

请只返回 JSON 对象。""",
            )
        )

        self.register(
            PromptTemplate(
                key="answer_evaluation",
                version="1.0",
                description="Evaluate a user's answer against a question",
                system_template="""你是一个技术面试评分专家。请评估以下用户回答的质量。

问题：{{{question}}}
标准答案摘要：{{{reference_answer}}}
用户回答：{{{user_answer}}}

请输出以下 JSON：
- score: 0-100的整数
- feedback: 简短的反馈，指出优点和不足
- missing_points: 字符串数组，列出用户遗漏的关键点
- is_pass: true/false，表示回答是否达到及格标准（>=60分）

请只返回 JSON 对象。""",
            )
        )

        self.register(
            PromptTemplate(
                key="followup_generator",
                version="1.0",
                description="Generate follow-up questions based on a conversation",
                system_template="""你是一个技术面试官。根据以下对话历史，生成合适的追问。

原始问题：{{{original_question}}}
用户回答：{{{user_answer}}}

请生成 2-3 个追问，输出为 JSON 数组，每个追问包含：
- title: 追问标题
- content: 追问完整描述
- question_type: followup
- difficulty_level: 比原问题高 0-1 级

请只返回 JSON 数组。""",
            )
        )


# ── Singleton ──────────────────────────────────────────────────────

prompt_registry = PromptRegistry()
