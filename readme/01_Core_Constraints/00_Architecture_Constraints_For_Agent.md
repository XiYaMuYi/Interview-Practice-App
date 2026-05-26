# 00_Architecture_Constraints_For_Agent

## 系统架构与编码红线指南

> 本文件是本项目的最高级工程约束文档。
>
> 任何自动编码 Agent（包括 Claude Code、Cursor Agent、其他生成式编程工具）在开始编写、修改、重构、补全任何代码之前，**必须先阅读本规范**。
>
> 如果即将生成的代码会导致前后端耦合、跨层调用、AI 调用散落、数据模型失控或工作流不可维护，**必须停止生成**，并先向人类开发者提出架构重构建议。

---

## 1. 项目总原则

### 1.1 架构路线

本项目采用 **模块化单体（Modular Monolith）** 路线。

这意味着：
- 早期以单体方式快速交付
- 代码必须严格分层
- 模块之间通过接口与服务层协作
- 任何功能新增都必须优先考虑“可演进性”而不是“短期最快实现”

### 1.2 技术基调

- **后端**：Python + FastAPI + LangGraph
- **主模型供应商**：阿里云 DashScope 兼容 Claude API 风格的接入方式
- **Embedding**：本地 `D:\AI_Project\models\bge-small-zh-v1.5`
- **Reranker**：本地 `D:\AI_Project\models\bge-reranker-v2-m3`
- **数据库**：PostgreSQL + pgvector
- **前端**：Next.js + TypeScript + Tailwind CSS
- **部署原则**：MVP 阶段优先本地可运行、可调试、可扩展

### 1.3 不可违背的核心原则

- API 层只负责协议转换、参数校验、请求编排、响应封装
- 业务规则必须沉淀到 `services/` 或 `domain/`
- 数据库访问必须经过 `infra/` 或 repository 抽象
- 大模型调用必须经过统一 AI 网关
- LangGraph 节点必须可插拔、可替换、可测试
- 核心数据表必须保留扩展字段、版本字段、溯源字段
- 前端不得直接依赖后端内部领域模型，只能消费稳定 DTO
- 登录功能必须实现，但默认隐藏，由配置开关控制
- 文件解析、检索、生成、评价必须可独立演进
- 简历导入与面试题生成必须作为 MVP 核心能力之一，且必须与题库、标签、知识节点、学习记录体系复用同一套架构
- 所有循环型 Agent / ReAct 流程必须设置明确上限（例如 `max_turns` / `max_iterations` / `max_steps`），不得无限循环
- 当达到循环上限时，必须强制收敛并输出可解释的结束结果，不得继续消耗网络与模型资源
- 任何需要工具调用的多轮 Agent，都必须设计“退出条件”和“失败收敛路径”，避免无限追问、无限检索、无限重试
- 所有内嵌 Prompt 必须纳入版本管理，不能在代码里无版本地散落；每次修改提示词都要能追溯版本、模型和效果
- 所有 AI 输出结果都应携带 `prompt_version` / `prompt_key` / `model_version`，以便后续做结果回放、比较和轻量监控
- 中间件不是装饰品：`FastAPI` 负责异步入口，`Redis` 负责缓存与状态，`RabbitMQ` 负责长任务队列，`Kafka` 负责事件流与审计

---

## 2. 标准目录结构与职责

### 2.0 简历驱动面试生成的模块边界

简历驱动面试题生成不是一个临时脚本功能，而是本项目的核心输入能力之一。它必须被抽象为独立模块，并与现有知识库、题目管理、学习记录、对话评估能力共享同一底座。

建议新增以下能力模块：
- `resume/`：简历导入、解析、切片、结构化
- `interview_generator/`：基于简历内容生成面试题
- `profile_mapper/`：把简历技术栈、项目经历映射到知识节点与题库标签
- `question_router/`：决定题目生成策略、难度分布与出题顺序

### 2.1 推荐后端目录树

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── v1/
│   │   │   ├── routes/
│   │   │   │   ├── auth_routes.py
│   │   │   │   ├── import_routes.py
│   │   │   │   ├── question_routes.py
│   │   │   │   ├── study_routes.py
│   │   │   │   ├── chat_routes.py
│   │   │   │   └── ai_routes.py
│   │   │   └── __init__.py
│   │   └── deps.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── import_service.py
│   │   ├── resume_service.py
│   │   ├── question_service.py
│   │   ├── study_service.py
│   │   ├── chat_service.py
│   │   ├── ai_service.py
│   │   └── retrieval_service.py
│   ├── domain/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── policies/
│   │   └── enums.py
│   ├── infra/
│   │   ├── db/
│   │   ├── repositories/
│   │   ├── llm/
│   │   │   ├── gateway.py
│   │   │   ├── prompt_registry.py
│   │   │   ├── config.py
│   │   │   └── providers/
│   │   ├── parsers/
│   │   ├── vectorstore/
│   │   └── storage/
│   ├── graphs/
│   │   ├── interview_graph.py
│   │   ├── explanation_graph.py
│   │   ├── review_graph.py
│   │   └── nodes/
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── exceptions.py
│   └── tests/
```

### 2.2 各层职责

#### `api/`
只允许做：
- 接收请求
- 校验参数
- 调用 service
- 返回 DTO

禁止做：
- 写 SQL
- 直接调用 LLM
- 直接操作文件解析细节
- 写业务判断逻辑

#### `services/`
负责：
- 业务编排
- 调用多个领域能力
- 聚合返回结果
- 管理事务边界
- 决定流程走向

禁止做：
- 直接拼接 HTTP 响应
- 混入路由层逻辑
- 将 AI 调用散落到多个 service 之外

#### `domain/`
负责：
- 核心实体
- 领域规则
- 领域枚举
- 领域校验
- 数据契约

禁止做：
- 直接依赖 FastAPI
- 直接访问数据库
- 直接调用外部模型 API

#### `infra/`
负责：
- 数据库实现
- 仓储实现
- 文件系统
- 向量库
- 大模型供应商适配
- 文档解析器

禁止做：
- 引入业务流程判断
- 混入路由层职责
- 写面向用户的交互逻辑

#### `graphs/`
负责：
- LangGraph 状态机定义
- 节点组织
- 条件边
- 工作流编排
- 智能体执行路径

禁止做：
- 将业务逻辑写成不可维护的长函数
- 在节点中硬编码数据库访问细节
- 将所有 prompt 直接写死在节点函数内部

---

## 3. 严格分层调用规则

### 3.1 允许调用关系

- `api -> services`
- `services -> domain`
- `services -> infra`
- `services -> graphs`
- `graphs -> services` 或 `graphs -> infra` 的受控调用
- `infra -> domain`（只用于数据映射，不得反向依赖）
- `resume_service -> ai_service -> llmgateway` 的单向调用链必须明确，简历解析结果不得直接在路由层进入题目生成

### 3.2 禁止调用关系

以下调用一律禁止：

- `api -> infra`
- `api -> direct llm call`
- `api -> db query`
- `domain -> api`
- `domain -> services`
- `domain -> infra`
- `infra -> api`
- `infra -> services`（除非通过明确定义的接口或适配器）
- `graph node -> hardcoded http request to business api`

### 3.3 强制原则

如果实现某个功能时，你发现自己必须跨层直接调用，请先停下来检查架构设计。**跨层调用不是捷径，而是债务。**

---

## 4. 数据库设计红线

### 4.1 核心表必须预留扩展字段

以下表结构必须至少包含：
- `metadata` JSONB
- `source_id`
- `version`
- `model_version`
- `prompt_version`
- `created_at`
- `updated_at`

必要时还应保留：
- `deleted_at`
- `status`
- `source_type`
- `origin_payload`

### 4.2 原则要求

- 不允许把所有额外信息硬塞进少数几个固定字段
- 不允许因为 MVP 简化而移除扩展能力
- 不允许将模型输出结果“只写一次，不可追溯”
- 不允许缺失来源信息

### 4.3 溯源字段必须保留

所有由 AI 生成或 AI 参与生成的数据，都至少应支持追溯：
- 输入来源
- 生成时间
- 使用模型
- prompt 版本
- 结果版本

---

## 5. AI 与大模型调用红线

### 5.1 绝对禁止的写法

以下写法一律禁止：
- 在业务代码中直接写 `llm.invoke()`
- 在路由函数中直接拼 prompt 后发模型请求
- 在多个 service 中各自维护一套不同模型调用方式
- 在节点函数里散落 provider 特定逻辑

### 5.2 强制统一入口

所有模型调用必须通过：
- `LLMGateway`
- `PromptRegistry`
- `ModelProvider` 适配层

### 5.3 调用规范

- `LLMGateway` 负责统一输入、输出、重试、日志、监控、错误封装
- `PromptRegistry` 负责集中管理 prompt 模板与版本
- `ModelProvider` 负责对接具体模型供应商

### 5.4 基础配置要求

- 所有模型供应商信息必须来自 `.env`
- 任何 baseurl、api key、model 名称都不能硬编码在业务代码里
- 必须预留云端与本地模型切换开关

---

## 6. LangGraph 工作流设计规范

### 6.1 Node 设计要求

所有节点必须满足：
- 独立函数或类实现
- 单一职责
- 可插拔
- 可替换
- 可单测
- 输入输出清晰

### 6.2 State 设计要求

LangGraph 的 `State` 必须：
- 使用明确 Schema
- 定义每个字段的类型与含义
- 避免无约束大字典
- 支持版本演进

### 6.3 条件边设计要求

条件边必须基于清晰的业务条件：
- 题目太难 -> 进入讲解模式
- 回答错误 -> 进入复盘模式
- 信息不足 -> 回到提取或追问节点
- 达到掌握阈值 -> 进入下一题或提升难度
- 超过追问轮次 -> 强制收束到评价或持久化节点
- 简历中命中高相关技术栈 -> 进入简历驱动出题分支
- 简历中仅有宽泛描述 -> 进入补全追问分支，从项目细节继续挖掘

---

## 7. 登录与权限红线

### 7.1 功能要求

- 登录功能必须存在
- 认证与授权基础设施必须预留
- 默认不在 UI 中开放入口
- 通过配置开关决定是否启用公开访问

### 7.2 约束要求

- 单用户模式可以作为默认工作模式
- 但后端不得把身份体系做死成“没有用户”
- 所有用户相关表要预留 `user_id`
- 后续开放时不得重写主数据模型

---

## 8. 给自动编码 Agent 的核心原则

当你（AI Coder）在执行任何开发任务前，必须首先阅读本规范。

如果你发现即将生成的代码会导致前后端耦合、跨层调用、AI 调用散落、数据库结构失去扩展性，或违背上述分层原则，你必须停止生成，并向人类开发者提出架构重构建议。

你不能为了“快速完成任务”而牺牲系统边界。

你不能把临时代码直接写成长期架构。

你不能把业务逻辑塞进路由层。

你不能把模型调用散落在任意函数中。

你不能把 LangGraph 节点写成不可替换的巨型过程。

你必须优先维护可演进性、可读性、可测试性和可替换性。

如果当前任务无法在不破坏以上原则的前提下完成，你必须先提出重构方案，再继续写代码。

---

## 9. 最终结语

本项目不是一个一次性脚本，而是一个可演进的 AI 面试知识系统。

任何代码提交都必须对未来负责。

任何短期便利都不能以牺牲架构边界为代价。

任何自动编码 Agent 都必须服从本规范。
