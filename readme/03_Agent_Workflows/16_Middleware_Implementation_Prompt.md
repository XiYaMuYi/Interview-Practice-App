# 16_Middleware_Implementation_Prompt

## Claude Code 执行指示

请先阅读以下文档，再开始修改代码：

1. `readme/README.md`
2. `readme/01_Core_Constraints/00_Architecture_Constraints_For_Agent.md`
3. `readme/01_Core_Constraints/01_System_Architecture.md`
4. `readme/02_Implementation_Guides/14_Streaming_Task_Pipeline_Architecture.md`
5. `readme/02_Implementation_Guides/15_Prompt_Version_Management_and_Observability.md`
6. `readme/02_Implementation_Guides/16_Resume_Workflow_Refactor_Spec.md`
7. `readme/02_Implementation_Guides/17_Middleware_Architecture_and_Performance.md`
8. `readme/03_Agent_Workflows/13_Backend_Agent_RAG_Code_Reading_Guide.md`

---

## 任务目标

请把当前项目中已经接入或预留的中间件能力真正落地，让它们在 MVP 阶段也能体现真实价值，而不是只停留在“有客户端、有开关、能启动”的层面。

本项目当前涉及的中间件有：
- `FastAPI`
- `Redis`
- `RabbitMQ`
- `Kafka`

你的目标是把这些工具真正融入到项目架构里，让它们分别承担清晰职责，并在本地 Docker / 个人部署场景下保持轻量、稳定、可降级。

---

## 中间件职责要求

### 1. FastAPI
FastAPI 应作为：
- 异步 API 入口
- 文件上传入口
- SSE 输出入口
- 任务状态查询入口
- 轻量业务编排入口

要求：
- 路由层保持轻薄
- 不在路由层写复杂业务
- 长任务统一走任务化 / SSE / 状态查询

### 2. Redis
Redis 应作为：
- 热缓存
- 会话状态缓存
- 任务进度缓存
- 高频结果复用层

优先缓存：
- 简历摘要
- 题目抽取结果
- 首题
- 追问
- 讲解结果

要求：
- TTL 保守
- 不缓存超大原文
- 失败必须 graceful fallback
- 本地资源占用要可控

### 3. RabbitMQ
RabbitMQ 应作为：
- 长任务队列
- 批量处理队列
- 重试队列
- 后台任务分发器

适用场景：
- 长文档解析
- 简历批量生成题目
- 批量知识节点处理
- 重试耗时任务

要求：
- 真正挂到长任务路径上
- 不是只初始化客户端
- 可以降级为同步模式
- 避免无节制重试

### 4. Kafka
Kafka 应作为：
- 事件流
- 审计流
- 埋点流
- 任务生命周期记录管道

适用场景：
- 任务创建/开始/完成/失败
- prompt 版本变化
- 缓存命中/失效
- 长任务分块过程

要求：
- 不能只是空壳
- 可以先预留接口
- 如果本地没有 Kafka，则可切换内存事件后端

---

## 需要优先检查和改造的代码

### 基础设施层
- `backend/app/infra/cache/redis_client.py`
- `backend/app/infra/messaging/rabbit_client.py`
- `backend/app/core/config.py`

### 服务层
- `backend/app/services/task_manager.py`
- `backend/app/services/import_service.py`
- `backend/app/services/ai_service.py`
- `backend/app/services/question_service.py`

### API 层
- `backend/app/api/v1/routes/import_routes.py`
- `backend/app/api/v1/routes/question_routes.py`
- `backend/app/api/v1/routes/ai_routes.py`
- `backend/app/api/v1/routes/resume_routes.py`

### 工作流层
- `backend/app/graphs/interview_graph.py`
- `backend/app/graphs/explanation_graph.py`
- `backend/app/graphs/review_graph.py`

---

## MVP 阶段必须体现的效果

不要只做“挂件”，要让人看出性能收益：

1. **重复请求命中缓存**
   - 同一简历、同一首题、同一追问、同一讲解应有复用

2. **长任务不阻塞请求**
   - 批量生成、长文本解析进入队列后，前端立刻可见任务状态

3. **过程可观测**
   - 任务状态、缓存命中、失败重试、事件流都应可追踪

4. **资源占用可控**
   - Redis 不应无限增长
   - 队列不应无限积压
   - 本地环境不应因中间件过重而崩掉

---

## 具体改造要求

### 1. Redis 改造
- 找出适合缓存的关键结果
- 设置合理 TTL
- 避免缓存过长文本或大对象
- 提供缓存命中日志
- 提供缓存失效和手动清理能力

### 2. RabbitMQ 改造
- 把真正耗时的任务挂入队列
- 提供任务重试和失败处理
- 限制并发和预取
- 保持同步降级能力

### 3. Kafka 改造
- 把关键流程事件抽象成统一发布接口
- 先确保事件可以被记录
- 如果暂时不接 Kafka，至少预留统一事件发布层

### 4. FastAPI 改造
- 保持路由层轻薄
- 所有长任务改为提交任务 + 查状态 + SSE 订阅
- 上传接口和流式接口要拆清楚

### 5. MVP 约束
- 当前项目还应视为 MVP 向小型完整项目演进阶段
- 不能只加功能，不体现性能收益
- 不能只加中间件，不改业务链路
- 所有改造应优先落在最能体现收益的路径上

---

## 你最后要输出的内容

请在完成代码修改后，输出：
- Redis 实际缓存了哪些内容
- RabbitMQ 实际承接了哪些长任务
- Kafka 或事件层记录了哪些事件
- FastAPI 哪些接口改成了异步 / SSE / 状态查询
- 哪些地方体现了 MVP 阶段的真实性能提升
- 哪些地方是预留接口，后续可继续扩展

---

## 最终目标

这次重构的目标不是“把中间件都挂上”，而是：
- 让中间件各司其职
- 让 MVP 阶段也能看到性能收益
- 让项目从单纯功能堆叠转向小型完整系统的可演进架构
- 让本地部署保持稳定、可控、可降级

请开始按上述要求修改代码。