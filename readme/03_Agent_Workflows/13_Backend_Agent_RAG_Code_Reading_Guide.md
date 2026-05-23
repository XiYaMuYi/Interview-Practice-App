# 阅读说明

## 后端 Agent / RAG 代码阅读路线图

> 这份说明用于指导你按正确顺序阅读后端代码，先理解整体架构，再看 Agent 工作流，再看业务服务，最后看底层检索与持久化。
>
> 阅读目标不是“把每个文件都看一遍”，而是先建立清晰的系统认知：
> - 哪些文件负责 Agent 编排
> - 哪些文件负责业务逻辑
> - 哪些文件负责 RAG 检索
> - 哪些文件负责状态与数据结构
> - 哪些文件负责数据库 / 向量 / LLM 基础设施

---

## 1. 阅读总顺序

建议按下面顺序阅读：

1. `backend/app/graphs/states.py`
2. `backend/app/graphs/interview_graph.py`
3. `backend/app/graphs/explanation_graph.py`
4. `backend/app/graphs/review_graph.py`
5. `backend/app/graphs/nodes/interview_nodes.py`
6. `backend/app/services/ai_service.py`
7. `backend/app/services/question_service.py`
8. `backend/app/services/import_service.py`
9. `backend/app/infra/vectorstore/pgvector_store.py`
10. `backend/app/infra/llm/gateway.py`
11. `backend/app/infra/llm/prompt_registry.py`
12. `backend/app/api/v1/routes/*.py`
13. `backend/app/infra/repositories/*`

这个顺序的核心原则是：
- 先看状态，再看流程
- 先看流程，再看节点
- 先看节点，再看服务
- 先看服务，再看基础设施
- 最后看 API 接口如何把整套能力暴露给前端

---

## 2. 文件级阅读说明

### 2.1 `backend/app/graphs/states.py`

#### 职责
这是 LangGraph 的状态定义文件，所有工作流共享同一个 `InterviewState`。

#### 你要看什么
- `InterviewState` 里有哪些字段
- 哪些字段是输入类
- 哪些字段是解析与理解类
- 哪些字段是生成与交互类
- 哪些字段是决策与控制类

#### 你应该建立的理解
这个文件定义了整个 Agent 系统“能记住什么、能传什么、能改什么”。

#### 重点结论
如果你看懂了 `states.py`，你就已经知道 Agent 工作流里的状态是怎么流转的。

---

### 2.2 `backend/app/graphs/interview_graph.py`

#### 职责
这是模拟面试主工作流图，负责把各个节点串成一个状态机。

#### 你要看什么
- 节点顺序：`extractor -> classifier -> retriever -> interviewer / explainer -> evaluator -> persister`
- 条件边的路由规则
- 什么条件会进入讲解
- 什么条件会进入追问
- 什么条件会进入保存

#### 你应该建立的理解
这个文件是 Agent 的“总导演”。它不负责生成内容，而负责决定下一步去哪里。

#### 重点结论
如果你想知道“为什么这个系统会先讲解、再追问、再评分”，答案就在这里。

---

### 2.3 `backend/app/graphs/explanation_graph.py`

#### 职责
这是简化版讲解链路，适合只做“提取 → 分类 → 讲解 → 落库”的场景。

#### 你要看什么
- 线性链路是如何定义的
- 为什么它比完整面试图更简单
- 它在 MVP 早期承担什么作用

#### 你应该建立的理解
这是一个“轻量版 Agent”，主要服务于只需要讲解、不需要追问的用户场景。

#### 重点结论
如果你想理解系统如何从“面试系统”演化到“学习讲解系统”，看这个文件最合适。

---

### 2.4 `backend/app/graphs/review_graph.py`

#### 职责
这是复习调度图，负责基于答题质量安排下次复习时间。

#### 你要看什么
- `SM-2` 的简化逻辑
- `quality` 如何映射到复习间隔
- `mastery_level` 如何变化
- `next_review_at` 如何生成

#### 你应该建立的理解
这个文件定义了学习闭环中“答完之后怎么回访”的策略。

#### 重点结论
它是学习系统的时间调度器，不是面试流程本身。

---

### 2.5 `backend/app/graphs/nodes/interview_nodes.py`

#### 职责
这是 LangGraph 节点实现，是 Agent 的具体动作层。

#### 你要看什么
- `extractor_node`
- `classifier_node`
- `retriever_node`
- `explainer_node`
- `interviewer_node`
- `evaluator_node`
- `persister_node`

#### 你应该建立的理解
每个节点都是一个职责单一的小功能，它们共同组成工作流。

#### 推荐记忆方式
- `extractor`：提取原始内容
- `classifier`：给内容打标签
- `retriever`：找相关内容
- `explainer`：生成讲解
- `interviewer`：进行追问
- `evaluator`：评分反馈
- `persister`：告诉业务层保存

#### 重点结论
这就是你系统的 Agent 核心执行层。

---

### 2.6 `backend/app/services/ai_service.py`

#### 职责
这是 AI 业务编排层，负责对外提供讲解、面试、评分、追问等能力。

#### 你要看什么
- `explain_question`
- `start_interview`
- `evaluate_answer`
- `generate_followup`
- `handle_interview_turn`

#### 你应该建立的理解
这个服务是业务入口，它并不直接写模型调用细节，而是统一通过 `llm_gateway` 调用模型。

#### 重点结论
如果说 `interview_nodes.py` 是动作层，那么 `ai_service.py` 就是业务编排层。

---

### 2.7 `backend/app/services/question_service.py`

#### 职责
这是题库与 RAG 的核心业务服务。

#### 你要看什么
- `create_question`
- `classify_question`
- `semantic_search`
- `embed_question`

#### 你应该建立的理解
这里负责把题目从“原始输入”变成“可管理、可检索、可复习”的结构化数据。

#### 重点结论
如果你要理解题目如何进入知识库、如何打标签、如何做语义检索，就看这个文件。

---

### 2.8 `backend/app/infra/vectorstore/pgvector_store.py`

#### 职责
这是底层向量检索实现。

#### 你要看什么
- `upsert`
- `search_similar`
- `delete`

#### 你应该建立的理解
它负责把 embedding 存进 PostgreSQL，并通过 pgvector 做相似度搜索。

#### 重点结论
这是 RAG 检索的基础设施层，不能混业务规则。

---

### 2.9 `backend/app/infra/llm/gateway.py`

#### 职责
统一 LLM 调用入口。

#### 你要看什么
- 如何封装 provider
- 如何做 chat / json / prompt-based 调用
- 如何统一重试、错误处理、日志和模型切换

#### 你应该建立的理解
业务层不应该直接依赖具体模型提供方，所有调用应通过网关层进入。

#### 重点结论
这是“模型供应商可替换”的关键封装点。

---

### 2.10 `backend/app/infra/llm/prompt_registry.py`

#### 职责
集中管理 prompt 模板与版本。

#### 你要看什么
- prompt 是如何命名的
- 如何做版本管理
- 哪些任务依赖 prompt registry

#### 你应该建立的理解
prompt 不应该散落在业务代码里，而应该集中管理，便于演进和回滚。

#### 重点结论
这部分是后续调 prompt、换版本、做 A/B 测试的重要基础。

---

### 2.11 `backend/app/api/v1/routes/*.py`

#### 职责
这是后端暴露给前端的 HTTP 接口层。

#### 你要看什么
- 导入接口如何调用服务
- 题目接口如何分页
- AI 接口如何触发工作流
- 简历接口如何进入解析与出题流程

#### 你应该建立的理解
路由层只做协议转换，不做业务决策。

#### 重点结论
如果你发现路由里出现复杂业务逻辑，那通常是坏味道。

---

### 2.12 `backend/app/infra/repositories/*`

#### 职责
仓储层负责具体数据库读写。

#### 你要看什么
- 如何分页
- 如何过滤
- 如何软删除
- 如何做关联查询

#### 你应该建立的理解
服务层调用仓储层，仓储层调用数据库，职责必须清晰。

#### 重点结论
这里是数据读写的最后一层，不应该携带 UI 或 Agent 逻辑。

---

## 3. 三条核心理解链路

### 3.1 Agent 链路
`states.py` → `interview_graph.py` → `interview_nodes.py` → `ai_service.py`

你要理解：
- 状态怎么流转
- 节点怎么执行
- 业务怎么封装
- 模型怎么被统一调用

---

### 3.2 RAG 链路
`question_service.py` → `pgvector_store.py` → `llm_gateway.py` → `prompt_registry.py`

你要理解：
- 题目如何结构化
- embedding 如何存储
- 相似题如何召回
- prompt 如何组织

---

### 3.3 前后端接口链路
`routes/*.py` → `services/*.py` → `graphs/*.py` → `infra/*`

你要理解：
- 前端请求如何进入后端
- 后端如何把请求交给服务和工作流
- 最后如何落库或返回结构化结果

---

## 4. 推荐阅读方法

### 第一次阅读
目标是“知道系统有哪些层”。不要急着抠细节。

### 第二次阅读
目标是“知道一次面试从输入到输出怎么流转”。

### 第三次阅读
目标是“知道哪里是 Agent，哪里是 RAG，哪里是业务层”。

### 第四次阅读
目标是“看懂前端为什么要分页、为什么要统一 UI、为什么要有简历驱动入口”。

---

## 5. 你可以用这个顺序形成心智模型

1. `InterviewState` 是什么状态
2. graph 怎么路由
3. node 怎么执行
4. service 怎么编排
5. repository 怎么存取
6. vectorstore 怎么检索
7. gateway 怎么调用模型
8. prompt registry 怎么管理提示词
9. routes 怎么把能力交给前端

---

## 6. 总结

如果把这个系统类比成一个人：

- `graphs/` 是大脑里的思考流程
- `nodes/` 是具体的思考动作
- `services/` 是做决定和协调的中枢
- `repositories/` 是记忆和存储
- `vectorstore/` 是联想与相似记忆
- `llm/gateway` 是和外部大模型沟通的嘴
- `routes/` 是和前端说话的门面

这份阅读说明的目标，就是帮你先把这套结构看懂，再去改代码就不会乱。
