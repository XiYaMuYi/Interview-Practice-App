"""LangGraph 状态定义文件。

这个文件是后端 Agent / RAG 工作流的“共享状态说明书”。
如果你想先理解简历、题目、讲解、追问、复习这些流程是怎么把
数据在各个节点之间传递的，应该先看这里。

所有 LangGraph 工作流都复用同一个 `InterviewState` 状态结构。
它本质上是一个 TypedDict，含义是：
- 每个节点只负责读取和更新自己关心的字段
- LangGraph 会把局部更新合并回总状态
- 状态字段必须尽量稳定，避免随意改名或乱加字段

这个文件对应 `readme/阅读说明.md` 中的“状态层”章节。
"""

from typing import Any

from typing_extensions import TypedDict


class InterviewState(TypedDict, total=False):
    """后端 Agent / RAG 工作流的统一状态容器。

    设计原则：
    1. 这里不是业务实体表，而是工作流运行时状态。
    2. 节点之间通过这个状态对象传递上下文。
    3. 允许部分字段缺失，因此使用 `total=False`。
    4. 新增字段前要先想清楚：这个字段属于输入、理解、生成、
       评价还是控制。
    """

    # ── 输入层：工作流最开始收到的原始内容 ───────────────────────
    input_text: str
    # 输入来源：例如上传、粘贴、对话、手动输入。
    input_source: str
    # 会话 ID：用于区分一次完整对话或一次训练流程。
    session_id: str
    # 用户 ID：MVP 阶段可以为空，但必须预留多用户能力。
    user_id: str
    # 文件 ID：当输入来自文件上传时用于追踪源文件。
    file_id: str
    # 题目 ID：当状态已经绑定到数据库中的题目时使用。
    question_id: str
    # 本次工作流运行 ID：用于日志、追踪、排错。
    run_id: str

    # ── 解析与理解层：把原始输入变成结构化信息 ─────────────────
    # 节点抽取后的中间结构，通常包含原文切片、识别结果等。
    parsed_content: dict
    # 标准化后的题目文本。
    question_text: str
    # 题型：概念题、对比题、场景题、架构题、项目题、追问题等。
    question_type: str
    # 领域：RAG、Agent、LangGraph、Prompting、VectorDB、Deployment 等。
    domain_type: str
    # 难度等级：建议 1-5。
    difficulty_level: int
    # 标签列表：用于筛选、统计、推荐和知识组织。
    tags: list[str]
    # 知识点列表：题目涉及到的关键知识点。
    knowledge_points: list[str]
    # 前置知识：回答当前题目之前应先理解的内容。
    prerequisites: list[str]
    # 检索命中结果：RAG 检索或相似题召回的结果集合。
    retrieval_hits: list[dict]

    # ── 生成与交互层：讲解、追问、回答、评分 ────────────────────
    # 一句话核心答案：适合快速浏览或卡片展示。
    answer_short: str
    # 面试版答案：适合 1-2 分钟口头回答。
    answer_detail: str
    # 深入讲解：适合学习和复盘。
    explanation: str
    # 常见易错点：帮助用户避免踩坑。
    common_pitfalls: str
    # 追问题目列表：面试官继续追问时使用。
    followup_questions: list[str]
    # 聊天历史：保存当前会话中的对话上下文。
    chat_history: list[dict]
    # 用户回答：当前轮次提交的回答文本。
    user_answer: str
    # 用户分数：通常为 0-100 的评分结果。
    user_score: int
    # 反馈：对当前回答的文字反馈或点评。
    feedback: str
    # 结构化评价结果：如缺失点、是否通过等。
    evaluation: dict

    # ── 决策与控制层：决定下一步走向哪里 ─────────────────────────
    # 下一步动作：classify / retrieve / interview / evaluate / save / error / ask
    next_action: str
    # 是否需要复习：用于学习计划和错题管理。
    review_needed: bool
    # 掌握度：建议 1-5，和复习策略联动。
    mastery_level: int
    # 是否需要落库：由 persister 节点或 service 层处理。
    persist_flag: bool
    # 状态版本：用于后续状态结构升级和兼容。
    state_version: str
    # 扩展元信息：例如 followup_turns、max_turns、interval_days 等。
    metadata: dict[str, Any]
    # 错误信息：当某个节点失败时记录原因。
    error_message: str
