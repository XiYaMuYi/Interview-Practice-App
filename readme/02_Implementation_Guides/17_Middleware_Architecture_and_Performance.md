# 17_Middleware_Architecture_and_Performance

## 1. 目标

本项目已经接入了 `FastAPI`、`Redis`、`RabbitMQ`、`Kafka` 的基础设施入口，但当前状态仍然偏“轻量可运行”而不是“职责完全落地”。

本文件的目标不是让项目变重，而是让这些中间件在 MVP 阶段就真正产生价值：

- `FastAPI` 提供异步 API、SSE、任务状态查询与上传入口
- `Redis` 提供缓存、会话状态、任务进度与结果复用
- `RabbitMQ` 提供长任务队列、削峰、后台处理与重试
- `Kafka` 提供事件流、审计流、埋点流与后续分析能力

本文件定义它们在本项目中的职责边界、适用场景、性能预期和本地部署约束。

---

## 2. 当前实现现状

### 2.1 FastAPI

FastAPI 已经是当前后端的主入口框架，适合承载：
- 文件上传
- 任务提交
- SSE 流式响应
- 任务状态查询
- 结果分页查询

### 2.2 Redis

当前代码里已经有 `backend/app/infra/cache/redis_client.py`，并且采用“连接失败即降级”的轻量策略。

这说明 Redis 已经不是纯文档概念，而是已经进入代码，但仍需检查：
- 缓存 key 是否规范
- TTL 是否合理
- 大对象缓存是否会撑爆本地内存
- 是否有必要缓存所有结果
- 是否应该避免把长文本原文直接放入 Redis

### 2.3 RabbitMQ

当前代码里已经有 `backend/app/infra/messaging/rabbit_client.py`，同样是“连接失败即降级”的轻量策略。

这说明 RabbitMQ 已经预留了队列入口，但仍需检查：
- 是否真正挂到了长任务路径
- 是否只是有客户端，没有真正形成任务流
- 是否需要 ack / retry / dead-letter / prefetch 策略
- 是否在本地单机环境中引入了不必要的复杂度

### 2.4 Kafka

当前配置里已经预留了 Kafka 开关：
- `KAFKA_BOOTSTRAP_SERVERS`
- `KAFKA_ENABLED`
- `EVENT_BACKEND`

但从代码角度看，Kafka 仍然是“待落地的事件总线入口”，需要进一步明确什么时候写 Kafka，什么时候只写内存事件或日志。

---

## 3. 中间件职责划分

### 3.1 FastAPI：请求入口与流式入口

FastAPI 的职责是：
- 接收请求
- 参数校验
- 调用 service
- 返回 JSON 或 SSE
- 承接上传和状态查询

FastAPI 不应该承担：
- 长时间阻塞计算
- 复杂队列调度
- 大量缓存拼装
- 重型事件分发

### 3.2 Redis：热缓存与状态缓存

Redis 的职责是：
- 简历摘要缓存
- 题目抽取缓存
- 首题缓存
- 追问缓存
- 讲解缓存
- 任务状态缓存
- 高频相似请求缓存

Redis 不应该承担：
- 长期原文存储
- 超大 JSON 结果长期堆积
- 所有任务历史的永久保存

### 3.3 RabbitMQ：长任务队列与重试队列

RabbitMQ 的职责是：
- 长文档解析任务
- 批量题目生成任务
- 批量知识节点抽取任务
- 大结果异步保存任务
- 失败重试任务

RabbitMQ 不应该承担：
- 实时状态展示
- 结果查询
- 长期审计存储

### 3.4 Kafka：事件流与审计流

Kafka 的职责是：
- 关键任务生命周期事件
- prompt 版本变化事件
- 生成结果事件
- 失败事件
- 重试事件
- 后续统计与分析事件

Kafka 不应该承担：
- 直接给前端做阻塞式结果返回
- 业务查询接口
- 任务状态主存储

---

## 4. MVP 阶段应该体现出的性能收益

中间件不是装饰品，MVP 里必须能体现实际效果。

### 4.1 Redis 应体现的收益

- 同一简历重复解析时减少重复调用
- 同一题目重复讲解时减少重复 LLM 请求
- 高频追问可直接命中缓存
- 任务状态读取不必每次都查主库

### 4.2 RabbitMQ 应体现的收益

- 长文档导入不阻塞 HTTP 请求
- 批量生成题目时可后台推进
- 失败任务可重试
- 高峰期请求可削峰

### 4.3 Kafka 应体现的收益

- 每个任务阶段都能留下事件记录
- 后续可以统计生成耗时、失败率、重试率
- 可以回放“为什么这次慢/失败/命中缓存”

### 4.4 FastAPI 应体现的收益

- 前端通过 SSE 实时看到进度
- 上传、状态查询、流式响应统一入口
- 路由层保持轻薄，业务逻辑集中在 service

---

## 5. 本地部署约束

由于本项目当前主要是个人本地或 Docker 环境部署，因此中间件设计必须满足以下约束：

### 5.1 Redis

- 默认关闭，必要时开启
- 连接失败必须 graceful fallback
- 缓存 TTL 必须保守，避免内存增长过快
- 不缓存超大原文
- 不缓存高频变动的长对象

### 5.2 RabbitMQ

- 默认关闭，必要时开启
- 任务队列必须能降级为同步模式
- 队列配置不能过度复杂
- 本地环境要避免无限重试和积压

### 5.3 Kafka

- 默认关闭，必要时开启
- 如果本地环境不具备 Kafka，可切换为内存事件后端
- 事件总线能力应可替代，但接口要统一

### 5.4 FastAPI

- 保持异步风格
- 避免路由层做重活
- SSE 推送必须可用

---

## 6. 推荐的代码落地点

### 6.1 后端基础设施

- `backend/app/infra/cache/redis_client.py`
- `backend/app/infra/messaging/rabbit_client.py`
- `backend/app/infra/event_bus/*`（若新增）
- `backend/app/services/task_manager.py`
- `backend/app/services/cache_service.py`（若新增）
- `backend/app/services/event_service.py`（若新增）

### 6.2 业务入口

- `backend/app/api/v1/routes/import_routes.py`
- `backend/app/api/v1/routes/question_routes.py`
- `backend/app/api/v1/routes/resume_routes.py`
- `backend/app/api/v1/routes/ai_routes.py`

### 6.3 任务流

- `backend/app/services/import_service.py`
- `backend/app/services/ai_service.py`
- `backend/app/graphs/*`

---

## 7. 建议的落地优先级

### 第一阶段：先让 Redis 真的有用

优先把以下内容缓存起来：
- 简历摘要
- 题目抽取结果
- 首题
- 追问
- 讲解结果

目标是先体现“重复请求更快”。

### 第二阶段：再让 RabbitMQ 接管长任务

把以下流程放入队列：
- 长文档解析
- 简历批处理
- 批量题目生成
- 大任务重试

目标是先体现“请求不阻塞”。

### 第三阶段：最后引入 Kafka 事件流

先记录任务关键事件：
- 创建
- 开始
- 分块处理
- 生成成功
- 失败
- 重试
- 完成

目标是先体现“可观测、可分析、可回放”。

---

## 8. 给 Claude Code 的执行红线

当 Claude Code 修改中间件相关代码时，必须先确认：

- Redis 是否会缓存过大对象
- TTL 是否合理
- RabbitMQ 是否真的在长任务上发挥作用
- Kafka 是否只是空壳
- FastAPI 路由是否保持轻薄
- MVP 是否确实体现出性能收益
- 是否仍然保留 graceful fallback

如果只是“加了依赖但没有实际收益”，说明实现不合格。

---

## 9. 最终结论

本项目现在已经从“纯 MVP 脚手架”进入“向小型完整项目演进”的阶段，但仍然应以 MVP 的方式控制范围。

正确方向不是堆中间件，而是：
- 让每个中间件承担明确职责
- 让每个中间件在 MVP 阶段就产生真实收益
- 让系统逐步具备完整项目的解耦与观测能力
