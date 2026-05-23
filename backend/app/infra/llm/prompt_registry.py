"""Prompt Registry。

这里负责管理后端所有可复用的 Prompt 模板。它的作用不是生成内容，
而是把提示词统一注册、统一版本化、统一检索。

每个模板都包含：
- key：唯一标识
- version：版本号
- system_template：系统提示词正文

模板中使用 `{{{variable}}}` 占位符，交给 LLM Gateway 做替换。
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PromptTemplate:
    """单个 Prompt 模板的结构定义。

    这个数据结构用于描述一个可复用 prompt 的元信息，方便后续：
    - 版本控制
    - 模型调优
    - 文档同步
    - 调试排查
    """

    key: str
    version: str
    system_template: str
    description: str = ""
    model_hints: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True


class PromptRegistry:
    """Prompt 模板注册中心。

    主要职责：
    - 启动时加载内置 prompt
    - 提供按 key 获取模板的能力
    - 允许后续注册新模板或替换旧模板
    - 给上层业务提供统一的 prompt 入口
    """

    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}
        self._load_builtin_prompts()

    # ── Public API ──────────────────────────────────────────────────

    def register(self, template: PromptTemplate) -> None:
        """注册一个 prompt 模板。

        如果 key 已存在，会直接覆盖旧版本。这样可以在开发阶段快速
        调整模板，而不必改调用逻辑。
        """
        self._templates[template.key] = template
        logger.debug(f"Registered prompt template: {template.key} v{template.version}")

    def get_system(self, key: str) -> str | None:
        """根据 key 获取系统提示词正文。

        上层大多数场景只需要拿到字符串模板，所以这里提供最常用的
        便捷接口。
        """
        tpl = self._templates.get(key)
        return tpl.system_template if tpl else None

    def get_template(self, key: str) -> PromptTemplate | None:
        return self._templates.get(key)

    def list_keys(self) -> list[str]:
        return list(self._templates.keys())

    async def list_versions(self, key: str, session) -> list[dict]:
        """查询某个 prompt key 的所有历史版本。

        从 `prompt_versions` 数据库表中查询，返回按创建时间倒序排列的
        版本列表。需要传入一个活跃的数据库 session。
        """
        from sqlmodel import select, col

        from app.domain.models import PromptVersion

        stmt = (
            select(PromptVersion)
            .where(PromptVersion.prompt_key == key)
            .order_by(col(PromptVersion.created_at).desc())
        )
        result = await session.exec(stmt)
        versions = result.all()
        return [
            {
                "id": v.id,
                "prompt_key": v.prompt_key,
                "prompt_version": v.prompt_version,
                "model_version": v.model_version,
                "created_at": v.created_at,
            }
            for v in versions
        ]

    async def save_version(
        self,
        key: str,
        version: str,
        content: str,
        model_hints: dict | None = None,
        description: str = "",
        session=None,
    ) -> dict:
        """将一个新的 prompt 版本写入 `prompt_versions` 表。

        这个方法不修改内存中的模板注册表，而是持久化到数据库，以便
        后续查询、比较和回溯。需要传入一个活跃的数据库 session。
        """
        from app.domain.models import PromptVersion

        pv = PromptVersion(
            prompt_key=key,
            prompt_content=content,
            prompt_version=version,
            model_version=model_hints.get("model") if model_hints else None,
            extra_data={"model_hints": model_hints, "description": description} if (model_hints or description) else None,
        )
        session.add(pv)
        await session.commit()
        await session.refresh(pv)
        logger.info(f"Saved prompt version: {key} v{version}")
        return {
            "id": pv.id,
            "prompt_key": pv.prompt_key,
            "prompt_version": pv.prompt_version,
            "model_version": pv.model_version,
            "created_at": pv.created_at,
        }

    # ── Builtin prompts ─────────────────────────────────────────────

    def _load_builtin_prompts(self) -> None:
        """加载内置 Prompt 模板。

        这里放的是项目启动时就应该可用的基础模板。MVP 阶段建议先
        把关键 prompt 都沉淀到这里，而不是分散写在各个 service 里。
        """
        self.register(
            PromptTemplate(
                key="question_extraction",
                version="2.0",
                description="Extract interview-style questions from source text (resume, notes, bulk text)",
                system_template="""你是一个资深技术面试题抽取器。请从以下文本中提取所有“可直接入题库”的问题。

要求：
1. 只提取与技术面试、知识考察、项目追问相关的问题
2. 每条结果必须是一个独立的问题，不要合并多个问题
3. 对每个问题输出以下 JSON 字段：
   - title: 问题的简短标题（最多50字）
   - content: 问题的完整描述
   - question_type: concept、compare、scenario、architecture、project、followup 之一
   - difficulty_level: 1-5 的整数
   - domain_type: RAG、Agent、LangGraph、Prompting、VectorDB、Deployment、Evaluation、General 之一
   - source_hint: 这道题来自文本中的哪一类信息（例如职责、项目、技术点、流程）

请以 JSON 数组格式返回，不要包含任何额外说明。如果没有可提取的问题，返回空数组 []。

源文本：
{{{text}}}""",
            )
        )

        self.register(
            PromptTemplate(
                key="question_extraction_raw",
                version="1.0",
                description="Extract raw question text from input (for InterviewState extractor node)",
                system_template="""你是一个面试题提取器。请从以下文本中提取出题目的核心内容。
如果文本是一个明确的问题，直接返回问题内容。
如果包含多个问题，提取第一个。
如果文本是笔记/描述而不是问题，标记 is_note=true。

输出JSON格式：
- question_text: 识别出的题目文本
- is_note: 是否是笔记而不是题目（true/false）

源文本：
{{{text}}}""",
            )
        )

        self.register(
            PromptTemplate(
                key="question_generation",
                version="1.0",
                description="Generate interview-style questions from candidate resume/experience",
                system_template="""你是一个资深技术面试官。请根据以下候选人的简历信息，生成高质量的技术面试题。

要求：
1. 根据候选人的技术栈、项目经验和职责，生成**相关且有针对性**的面试题
2. 题目应该覆盖：技术原理追问、项目深挖、场景设计、架构思考等维度
3. 生成 8-12 道题目，难度分布从基础到进阶（difficulty_level 1-5）
4. 每道题必须是一个独立的、可直接用于面试的问题
5. 不要生成泛泛而谈的问题（如"请介绍一下自己"），要聚焦技术细节

对每道题输出以下 JSON 字段：
- title: 问题的简短标题（最多50字）
- content: 问题的完整描述，包含必要的上下文和追问方向
- question_type: concept、compare、scenario、architecture、project、followup 之一
- difficulty_level: 1-5 的整数
- domain_type: RAG、Agent、LangGraph、Prompting、VectorDB、Deployment、Evaluation、General 之一
- source_hint: 这道题基于候选人简历中的哪个经历或技术点

请以 JSON 数组格式返回，不要包含任何额外说明。

候选人信息：
{{{text}}}""",
            )
        )

        self.register(
            PromptTemplate(
                key="question_classification",
                version="2.0",
                description="Classify an existing question into type, domain, difficulty, tags, knowledge_points",
                system_template="""你是一个技术面试分类专家。请对以下问题进行分类。

问题：{{{text}}}

请输出以下 JSON 字段：
- question_type: concept、compare、scenario、architecture、project、followup 之一
- domain_type: RAG、Agent、LangGraph、Prompting、VectorDB、Deployment、Evaluation、General 之一
- difficulty_level: 1-5 的整数
- tags: 字符串数组，最多5个
- knowledge_points: 知识点字符串数组
- prerequisites: 前置知识字符串数组

请只返回 JSON 对象，不要包含额外说明。""",
            )
        )

        self.register(
            PromptTemplate(
                key="question_explanation",
                version="1.0",
                description="Generate layered explanation for a question (explainer node)",
                system_template="""你是一个技术面试讲解专家。请对以下问题进行分层讲解。

问题：{{{question_text}}}
{{{context}}}

输出JSON格式：
- answer_short: 一句话核心答案
- answer_detail: 面试版回答（适合在1-2分钟内说完）
- explanation: 深入讲解，包括技术细节和易错点
- common_pitfalls: 常见易错点

请只返回 JSON 对象，不要包含额外说明。""",
            )
        )

        self.register(
            PromptTemplate(
                key="interview_followup",
                version="1.0",
                description="Generate follow-up questions during interactive interview (interviewer node)",
                system_template="""你是一个严格的技术面试官。根据以下信息生成追问。

原问题：{{{question_text}}}
用户回答：{{{user_answer}}}
难度等级：{{{difficulty}}}
当前追问轮次：{{{current_turn}}}
对话历史：
{{{history}}}

输出JSON格式：
- followup_questions: 1-2个追问问题
- evaluation: 对用户回答的简短评价

请只返回 JSON 对象，不要包含额外说明。""",
            )
        )

        self.register(
            PromptTemplate(
                key="interview_evaluation",
                version="1.0",
                description="Score and evaluate user answer in interview flow (evaluator node)",
                system_template="""你是一个技术面试评分专家。请评估以下用户回答。

问题：{{{question_text}}}
参考答案：{{{reference_answer}}}
用户回答：{{{user_answer}}}

输出JSON格式：
- score: 0-100的整数
- feedback: 简短反馈
- missing_points: 遗漏的关键点数组
- is_pass: true/false (>=60为pass)
- review_needed: 是否需要复习 (true/false)

请只返回 JSON 对象，不要包含额外说明。""",
            )
        )

        self.register(
            PromptTemplate(
                key="interview_single_eval",
                version="1.0",
                description="Lightweight evaluation for single interview turn (ai_service._evaluate_single_answer)",
                system_template="""你是一个技术面试官，面试练习场景请用鼓励性语气评估。

评分参考：80-100全面深入，60-79基本正确，40-59方向对但不完整，0-39偏离主题。

问题：{{{question_text}}}
回答：{{{user_answer}}}

请输出JSON，包含：
- score: 0-100的整数，先肯定亮点再指出改进方向
- feedback: 简短反馈，以鼓励为主
- is_pass: true/false (>=60为pass)

请只返回 JSON 对象，不要包含额外说明。""",
            )
        )

        self.register(
            PromptTemplate(
                key="interview_start",
                version="1.0",
                description="Generate first interview question to start a session",
                system_template="""你是一个经验丰富的技术面试官，风格友好、善于引导。请生成一个面试问题，要求：
- 从中等难度开始（difficulty_level 2-3），不要过于学术化
- 问题要开放式，鼓励候选人展示思考过程
- 适合AI应用工程师面试，聚焦实际工程能力
{{{context}}}

只输出面试题目本身，不要解释。""",
            )
        )

        self.register(
            PromptTemplate(
                key="interview_summary",
                version="1.0",
                description="Generate final interview evaluation summary",
                system_template="""面试已结束（原因：{{{convergence_reason}}}）。

当前题目：{{{question_text}}}
用户回答：{{{user_answer}}}

请给出最终面试评价，包括：
1. 总体评分
2. 回答亮点
3. 需要改进的地方
4. 后续学习建议""",
            )
        )

        self.register(
            PromptTemplate(
                key="knowledge_node_extraction",
                version="1.1",
                description="Extract knowledge nodes/concepts from text",
                system_template="""你是一个知识节点抽取专家。请从以下文本中提取最适合用于题目推荐和 RAG 检索的知识节点。

要求：
1. 识别文本中的核心概念、技术术语、前置知识和可追问主题
2. 每个节点要尽量短、可检索、可复用
3. 对每个节点输出以下 JSON 字段：
   - name: 知识节点名称
   - description: 简短描述
   - node_type: concept、prerequisite、topic 之一
   - depth_level: 1-3 的整数，1 为核心概念，3 为细分知识点
   - source_hint: 该节点来源于文本中的哪一部分

请以 JSON 数组格式返回，不要包含任何额外说明。

源文本：
{{{text}}}""",
            )
        )

        self.register(
            PromptTemplate(
                key="similarity_rerank",
                version="1.1",
                description="Rerank search results by relevance to a query",
                system_template="""你是一个搜索结果重排序专家。请根据用户查询，对以下候选问题按相关性从高到低排序。

用户查询：{{{query}}}

候选问题（JSON 数组）：
{{{candidates}}}

请输出以下 JSON：
- ranked_ids: 按相关性从高到低排列的问题 ID 数组（字符串格式）
- reasoning: 简要说明排序依据
- top_reason: 最相关前3项的共同特征

请只返回 JSON 对象，不要包含额外说明。""",
            )
        )

        self.register(
            PromptTemplate(
                key="answer_evaluation",
                version="2.0",
                description="Evaluate a user's answer against a question (with scoring anchors)",
                system_template="""你是一个技术面试评分专家。这是面试练习场景，请用鼓励性语气评估。

评分标准参考：
- 80-100分：回答全面准确，有深入理解和技术细节
- 60-79分：基本正确，核心要点覆盖但部分细节有缺失
- 40-59分：方向对但不够完整，需要补充关键知识点
- 0-39分：偏离主题或存在明显理解偏差

注意：
1. 面试场景允许口语化表达，不要求教科书级别的完美答案
2. 先肯定回答中的亮点，再指出可以改进的方向
3. feedback 应简洁、有建设性、以鼓励为主

问题：{{{question}}}
标准答案摘要：{{{reference_answer}}}
用户回答：{{{user_answer}}}

请输出以下 JSON：
- score: 0-100 的整数
- feedback: 简短反馈，先肯定优点再指出改进方向
- missing_points: 用户遗漏的关键点数组
- is_pass: true/false，表示是否达到及格标准（>=60 分）
- review_needed: true/false，是否需要复习
- followup_hint: 下一轮追问建议

请只返回 JSON 对象，不要包含额外说明。""",
            )
        )

        self.register(
            PromptTemplate(
                key="followup_generator",
                version="2.0",
                description="Generate follow-up questions with adaptive difficulty",
                system_template="""你是一个技术面试官，风格友好、善于引导。请根据原始问题和用户回答生成有针对性的追问。

原始问题：{{{original_question}}}
用户回答：{{{user_answer}}}

要求：
1. 如果用户回答得好（得分高），适当加深难度追问
2. 如果用户回答薄弱，先给提示再追问，不要直接跳到高难度
3. 追问难度最高不超过5级
4. 以鼓励和引导为主，帮助候选人展示更多知识

请生成 2-3 个追问，输出为 JSON 数组，每个追问包含：
- title: 追问标题
- content: 追问完整描述
- question_type: followup
- difficulty_level: 1-5的整数，根据回答质量动态调整，最高不超过5
- followup_goal: 追问目的（例如澄清、深挖、验证、补齐）

请只返回 JSON 数组，不要包含额外说明。""",
            )
        )

        self.register(
            PromptTemplate(
                key="resume_parsing",
                version="1.1",
                description="Parse a resume and extract structured information",
                system_template="""你是一个简历结构化解析专家。请从以下简历文本中抽取适合后续出题和知识映射的信息。

请输出以下 JSON 格式：
{
  "summary": {
    "name": "姓名（如无法识别则为null）",
    "title": "职位/头衔",
    "years_of_experience": 工作经验年数（整数，无法判断则为null）,
    "top_skills": ["核心技能1", "核心技能2", ...],
    "summary": "一段话总结该候选人的背景"
  },
  "experiences": [
    {
      "experience_type": "work / project / education",
      "company_or_project": "公司名或项目名",
      "role_title": "职位/角色",
      "start_date": "开始日期（如 2023-01）",
      "end_date": "结束日期（如 2024-06，至今则为null）",
      "description": "职责/项目描述",
      "tech_stack": {"languages": [...], "frameworks": [...], "tools": [...], "databases": [...]},
      "extracted_keywords": ["关键词1", "关键词2", ...],
      "confidence": 0.0-1.0 的置信度,
      "source_hint": "该经历来自简历中的哪一部分"
    }
  ]
}

要求：
1. 工作经历和项目经历分开，experience_type 必须明确区分
2. 技术栈尽量提取，并归类到 languages/frameworks/tools/databases
3. 如果没有某项信息则填 null，不要编造
4. experiences 按时间倒序排列
5. 结果要适合后续简历驱动出题、知识映射和检索

简历文本：
{{{text}}}""",
            )
        )


        self.register(
            PromptTemplate(
                key="review_summary",
                version="1.1",
                description="Generate a Chinese review summary from study statistics",
                system_template="""你是一个学习分析助手。请根据以下学习统计数据，生成一份适合面试备考者复盘的中文总结。

学习统计：
{{{records_summary}}}

薄弱知识点：
{{{weak_areas}}}

要求：
1. 总结学习进度和整体表现
2. 指出薄弱环节和需要加强的知识点
3. 给出积极反馈和鼓励
4. 语言简洁、专业、可执行
5. 总结控制在200-400 字
6. 结果应便于前端直接展示

请直接输出总结文本，不要包含 JSON 或其他格式。""",
            )
        )

        self.register(
            PromptTemplate(
                key="review_recommendations",
                version="1.1",
                description="Generate improvement recommendations from weak areas",
                system_template="""你是一个学习规划专家。请根据以下薄弱知识点和掌握度趋势，生成可执行的学习改进建议。

薄弱知识点：
{{{weak_areas}}}

掌握度趋势：{{{mastery_trend}}}

要求：
1. 生成 3-5 条具体可执行的改进建议
2. 每条建议要针对具体的薄弱环节
3. 建议要务实、可操作，例如复习顺序、练习方式、补充资料类型
4. 以字符串列表形式输出
5. 建议要便于前端直接展示并可用于后续推荐

请只返回 JSON 数组，格式为：["建议1", "建议2", ...]""",
            )
        )


# ── Singleton ──────────────────────────────────────────────────────

prompt_registry = PromptRegistry()
