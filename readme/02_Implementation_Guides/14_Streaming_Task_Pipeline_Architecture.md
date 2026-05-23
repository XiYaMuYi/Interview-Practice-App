# 14_Streaming_Task_Pipeline_Architecture

## 1. 目标

本项目的 AI 处理能力不能再依赖“用户上传一个大文件，后端一次性把整份内容喂给模型，最后一次性返回完整结果”的同步模式。

对于长文档、长简历、大题库、知识库构建、模拟面试追问、AI 讲解、复盘总结等场景，必须统一采用：

- 先切块
- 先入库
- 先建索引
- 再检索
- 再分模块喂给模型
- 再流式输出
- 再增量保存
- 再把中间结果实时推送给前端

本文件定义整个项目的统一流式任务管道规范。它不是某一个功能的实现细节，而是未来所有类似 AI 能力的全局架构原则。

---

## 2. 解决的问题

### 2.1 直接一次性输入的风险

如果把长文档一次性打包给大模型，容易出现：
- 上下文超限
- 输出过长
- 超时
- 任一步失败导致整批丢失
- 前端长时间空白等待

### 2.2 一次性输出的风险

如果要求模型一次性输出完整 JSON 或完整题库，容易出现：
- 输出结构不稳定
- 部分内容缺失
- 结果过大难以保存
- 一旦解析失败就全部作废

### 2.3 同步阻塞体验差

用户在前端看到的是：
- 一直转圈
- 一直等待
- 最后报错
- 或者结果全丢

这不符合一个可持续迭代的 AI 产品体验。

---

## 3. 统一架构原则

### 3.1 所有长任务必须任务化

任何会持续较久的 AI 处理，都不能放在一个同步 HTTP 请求里直接等待结果，而应该变成任务：
- 创建任务
- 返回任务 ID
- 后台执行
- 实时推送进度
- 增量保存结果
- 允许断点恢复

### 3.2 所有长文档必须切块

长文档不能直接整篇喂给模型，必须先做：
- 文本清洗
- 段落切分
- 语义切块
- 块级向量化
- 块级检索

### 3.3 所有 AI 产出必须增量保存

不能等到最后才一次性写库，而要做到：
- 每完成一个块就保存一个块
- 每生成一条题目就保存一条题目
- 每完成一个阶段就保存一个阶段结果

### 3.4 所有过程必须可恢复

任务中途失败后，已经保存的中间结果不能丢。用户重新进入时，应能从最后一个成功阶段继续，而不是从头再来。

### 3.5 所有过程必须可见

前端不能只看到“加载中”。必须看到：
- 当前阶段
- 当前块
- 已完成数量
- 总数量
- 失败原因
- 是否可重试

---

## 4. 统一任务管道模型

### 4.1 基础流水线

统一流程建议如下：

```text
用户上传 / 输入
    ↓
创建任务
    ↓
文件存储 / 原文存储
    ↓
切块 / 解析 / OCR
    ↓
写入结构化中间结果
    ↓
向量化并入向量库
    ↓
按块检索相关内容
    ↓
按模块喂给大模型
    ↓
流式输出中间结果
    ↓
增量保存题目 / 经历 / 讲解 / 追问
    ↓
任务完成，前端收到 done 事件
```

### 4.2 任务与事件分离

建议统一区分：
- **Task**：一个完整业务任务，例如简历解析、题库导入、知识库构建、面试生成
- **Event**：任务执行过程中的实时事件，例如 progress、chunk_saved、question_saved、done、error

### 4.3 状态与结果分离

- 任务状态保存“当前进度、当前阶段、是否完成、是否失败”
- 结果表保存“最终结构化结果、增量结果、版本信息”
- 事件流只负责实时反馈，不作为最终事实来源

---

## 5. 统一适用场景

### 5.1 简历解析

建议流程：
1. 上传简历
2. 切块
3. 逐块解析教育 / 工作 / 项目 / 技能
4. 增量保存 `Resume_Experiences`
5. 按经历逐块生成面试题
6. 流式推送进度和题目

### 5.2 题库导入

建议流程：
1. 导入长题库
2. 切块
3. 每块提取题目
4. 每块分类、打标、入库
5. 每批题目生成后立即通知前端

### 5.3 知识库构建

建议流程：
1. 导入文档
2. 切块
3. 提取知识节点
4. 生成 embeddings
5. 检索索引入库
6. 分批完成后汇总

### 5.4 面试题生成

建议流程：
1. 先检索简历或题库中的相关块
2. 按技术栈 / 项目经历 / 知识节点分模块生成
3. 每生成一道题就保存一道题
4. 前端实时追加题目卡片

### 5.5 模拟面试追问

建议流程：
1. 用户回答
2. 后端判断是否继续追问
3. 流式生成追问或提示
4. 每轮结束立即落库

### 5.6 AI 讲解 / 答案生成

建议流程：
1. 先给简版答案
2. 再给标准答案
3. 再给深入讲解
4. 每层结果都可单独保存

### 5.7 复盘 / 总结 / 报告

建议流程：
1. 先输出摘要
2. 再输出薄弱点
3. 再输出建议
4. 再输出可复习项

---

## 6. 流式输出的统一方式

### 6.1 推荐方式

对于前端实时体验，优先采用：
- SSE（Server-Sent Events）

原因：
- 实现简单
- 适合单向事件推送
- 浏览器支持好
- 适合任务进度、阶段结果、增量产出

### 6.2 备选方式

如果未来需要双向实时交互，可考虑 WebSocket。但在当前系统中，SSE 已足够覆盖：
- 进度通知
- 阶段事件
- 中间结果
- 完成事件
- 错误事件

### 6.3 事件类型建议

建议统一事件类型：
- `progress`：进度更新
- `chunk_saved`：一个切块或经历已保存
- `question_saved`：一道题已保存
- `record_saved`：一条学习记录已保存
- `warning`：非致命警告
- `error`：错误
- `done`：任务完成

### 6.4 前端展示原则

前端收到事件后应立即：
- 更新状态条
- 更新计数器
- 追加列表项
- 显示当前阶段
- 保留已成功结果

---

## 7. 后端统一实现建议

### 7.1 任务表

建议建立统一任务表，例如：
- `tasks`
- `task_events`
- `task_outputs`

任务表用于记录：
- 任务类型
- 输入来源
- 当前阶段
- 当前进度
- 是否完成
- 是否失败
- 错误原因
- 重试次数

### 7.2 事件表

事件表用于记录：
- 时间戳
- 任务 ID
- 事件类型
- 事件 payload
- 顺序号

### 7.3 增量结果表

增量结果表用于记录：
- 已保存的经历块
- 已生成的题目
- 已生成的讲解片段
- 已生成的追问链

### 7.4 服务层职责

服务层应该负责：
- 拆分任务
- 调用 LLM
- 保存中间结果
- 推送事件
- 失败重试

不应该在 service 里直接塞一大坨同步流程。

---

## 8. 前端统一实现建议

### 8.1 任务入口页

用户发起长任务后，前端应该拿到任务 ID，并跳转到任务详情页或任务进度页。

### 8.2 任务进度页

任务进度页应显示：
- 当前阶段
- 已完成数量
- 总数量
- 预计耗时
- 已生成结果列表
- 重试按钮

### 8.3 实时追加结果

前端应根据事件流实时追加：
- 新题目
- 新经历
- 新讲解
- 新追问
- 新复盘结论

### 8.4 失败可恢复

如果断开连接或页面刷新，前端应能通过任务 ID 重新拉取：
- 当前进度
- 已完成结果
- 错误信息
- 是否可继续

---

## 9. 与现有模块的关系

### 9.1 与 LangGraph 的关系

LangGraph 负责工作流编排，流式任务管道负责任务生命周期和结果推送。

两者关系是：
- LangGraph 管“内部推理流程”
- Streaming Task Pipeline 管“外部任务生命周期”

### 9.2 与 RAG 的关系

RAG 负责：
- 切块
- 检索
- 召回
- 上下文组织

流式任务管道负责：
- 把 RAG 的过程变成可见任务
- 把每个块的结果逐步展示给用户

### 9.3 与 Prompt Registry 的关系

Prompt Registry 管模板版本，流式任务管道管模板如何在分块流程中被逐步调用。

### 9.4 与前端分页的关系

分页解决的是“列表展示太多”的问题；流式任务管道解决的是“生成过程太慢、结果太大”的问题。

两者互补，不冲突。

---

## 10. 推荐的应用顺序

### 第一阶段
先把以下场景改成任务化和流式：
- 简历解析
- 长文档导入
- 题库批量导入

### 第二阶段
再扩展到：
- 面试题生成
- AI 讲解
- 追问链生成

### 第三阶段
最后扩展到：
- 复盘报告
- 学习路径生成
- 统计分析

---

## 11. 给 Claude Code 的执行原则

当 Claude Code 遇到任何“长输入、长输出、任务耗时长”的功能时，必须先问自己：

- 这个功能是否应该拆成任务？
- 是否应该先切块再处理？
- 是否应该流式推送进度？
- 是否应该增量保存？
- 是否应该支持断点恢复？
- 是否应该让前端实时显示阶段结果？

如果答案是“是”，就不要再写同步大请求模式。

---

## 12. 最终结论

这个项目未来所有类似能力，都应该统一走”任务化 + 流式反馈 + 增量保存 + 可恢复”的架构。

这不是一个可选增强，而是系统在面对长文档、大上下文和复杂 AI 生成任务时必须具备的基础能力。

---

## 13. Phase 1-6 完成总结

Phase 1 到 Phase 6 已全部实现，将本文档定义的原则落地为可运行的代码。

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | Task 模型 + DB migration (7c158c13231f) + TaskManager + SSE 基础设施 | ✅ 完成 |
| Phase 2 | 简历解析流式化：chunk_resume_text → parse_resume_stream + 增量 save | ✅ 完成 |
| Phase 3 | 题目导入流式化：chunk_import_text → import_text_stream + 增量 save | ✅ 完成 |
| Phase 4 | 前端 SSE Hook (useTaskEvents.ts) + Import 页面实时进度 UI | ✅ 完成 |
| Phase 5 | AI 讲解 / 评价 / 面试流式化：explain_stream / evaluate_stream / interview_turn_stream | ✅ 完成 |
| Phase 6 | 学习记录 / 复习 / 统计分页优化 + Stats 页面时间线 | ✅ 完成 |

---

## 14. SSE 流式 API 参考

所有流式端点均返回 `text/event-stream`，前端通过 POST + ReadableStream 消费（不使用 EventSource GET，因为需要传 body 参数）。

| 端点 | 方法 | Service 方法 | 事件类型 |
|------|------|-------------|----------|
| `POST /api/v1/resumes/{id}/parse-stream` | SSE | `resume_service.parse_resume_stream` | progress, chunk_saved, error, done |
| `POST /api/v1/import/text-stream` | SSE | `import_service.import_text_stream` | progress, question_saved, error, done |
| `POST /api/v1/ai/explain-stream` | SSE | `ai_service.explain_question_stream` | progress, content, error, done |
| `POST /api/v1/ai/evaluate-stream` | SSE | `ai_service.evaluate_answer_stream` | progress, result, error, done |
| `POST /api/v1/ai/interview/turn-stream` | SSE | `ai_service.handle_interview_turn_stream` | progress, evaluation, followup/summary, error, done |
| `GET /api/v1/resumes/tasks/{task_id}` | JSON | `task_manager.get_task` | 查询任务状态（普通 JSON 响应） |
| `GET /api/v1/import/tasks/{task_id}` | JSON | `task_manager.get_task` | 查询任务状态（普通 JSON 响应） |

### 事件数据格式

```
event: progress
data: {“task_id”: “...”, “phase”: “parsing”, “progress”: 0.45, “current”: “正在解析工作经历...”, “elapsed”: 3.2, “total_chunks”: 5, “chunk_index”: 2}

event: chunk_saved
data: {“task_id”: “...”, “chunk_index”: 2, “chunk_type”: “experience”, “experiences_count”: 3, “total”: 5}

event: done
data: {“task_id”: “...”, “status”: “done”, “elapsed”: 12.5, “experiences_count”: 8}

event: error
data: {“task_id”: “...”, “error”: “...”, “recoverable”: true}
```

---

## 15. 前端 SSE 消费模式

### 15.1 useTaskEvents Hook

位置：`web/src/hooks/useTaskEvents.ts`

该 hook 封装了 SSE 事件的完整消费逻辑：

```typescript
const { events, progress, status, currentPhase, currentMessage, error, isRecoverable, elapsed, totalGenerated, isConnected } = useTaskEvents(taskId);
```

**核心能力**：
- 自动连接 `/api/v1/tasks/{taskId}/events` 端点（通过 EventSource）
- 事件分类监听：progress, chunk_saved, question_saved, done, error
- 自动状态追踪：progress (0→1), status (pending→processing→done/failed), currentPhase
- 断线重连：最多 3 次，间隔 2 秒
- cleanup：组件卸载时自动关闭连接

### 15.2 前端状态机

```
pending → processing → [partial events] → done | failed
                                    ↑          |
                                    └── recoverable error ──→ retry
```

- **pending**: 任务刚创建，还未开始处理
- **processing**: 正在执行，持续收到 progress 事件
- **partial**: 中间结果事件（chunk_saved, question_saved, content, result 等）
- **done**: 收到 `done` 事件，progress = 1
- **failed**: 收到不可恢复的 `error` 事件

### 15.3 POST SSE 与 GET SSE 的区别

实际实现中，后端路由直接返回 `StreamingResponse(event_gen)`，前端有两种消费方式：

1. **GET + EventSource**（useTaskEvents 当前方式）：适用于已有 task_id 后查询进度
2. **POST + ReadableStream**（导入页面实际使用）：POST 请求 body 携带参数，读取 response.body 的 ReadableStream 逐行解析 SSE 事件

第二种方式是 import page 中采用的方式，因为 POST SSE 需要传 body（文本内容、配置参数等），而 EventSource 只支持 GET。

---

## 16. 已建立的约束与模式

### 16.1 Service 方法签名

所有流式 service 方法统一返回 `(task_id, event_generator)` 二元组：

```python
async def parse_resume_stream(self, resume_id: UUID) -> tuple[UUID, AsyncGenerator[str, None]]
async def import_text_stream(self, text: str) -> tuple[UUID, AsyncGenerator[str, None]]
async def explain_question_stream(self, ...) -> tuple[UUID, AsyncGenerator[str, None]]
async def evaluate_answer_stream(self, ...) -> tuple[UUID, AsyncGenerator[str, None]]
async def handle_interview_turn_stream(self, ...) -> tuple[UUID, AsyncGenerator[str, None]]
```

### 16.2 SSE 事件格式化

每个流式方法内部定义 `_sse()` 辅助函数，将 dict 格式化为标准 SSE 字符串：

```python
def _sse(event_type: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f”event: {event_type}\ndata: {payload}\n\n”
```

### 16.3 路由层直接返回 StreamingResponse

路由不再使用 `sse_event_stream(task_manager, task_id)` 的订阅模式，而是直接将 service 返回的 `event_gen` 传给 `StreamingResponse`：

```python
@router.post(“/{resume_id}/parse-stream”)
async def parse_resume_stream(resume_id: UUID, session: DbSession):
    service = ResumeService(session)
    task_id, event_gen = await service.parse_resume_stream(resume_id)
    return StreamingResponse(event_gen, media_type=”text/event-stream”, ...)
```

这意味着 event_generator 是**直接 pass-through**，不经过 TaskManager 的 subscribe/notify 队列。TaskManager 仍然负责创建/更新 Task 记录（持久化进度），但 SSE 事件流由 generator 直接 yield 给 HTTP 响应。

### 16.4 任务创建规范

所有长时间运行的 AI 操作都创建一个 Task 记录：

```python
task_manager = TaskManager(self.session)
task = await task_manager.create_task(task_type=”resume_parse”, source_id=str(resume_id))
```

Task 类型包括：`resume_parse`, `import_extract`, `explanation`, `evaluation`, `interview_turn`。

### 16.5 增量保存

每个 chunk/块处理完毕后立即调用 `session.flush()`，确保即使后续块失败，已处理的结果也已持久化：

```python
self.session.add(exp)
await self.session.flush()  # 每解析一个 chunk 就 flush
```

### 16.6 错误处理

所有流式方法的 try/except 块统一：

1. catch 异常
2. 更新 task status 为 “failed”
3. 写入 error_message 到 task
4. yield error 事件，标记 recoverable 标志

```python
except Exception as e:
    logger.error(f”Stream failed: {e}”)
    await task_manager.update_task(task_id, status=”failed”, progress=0.0, error_message=str(e)[:500])
    yield _sse(“error”, {“task_id”: str(task_id), “error”: str(e), “recoverable”: False})
```

### 16.7 向后兼容

所有流式端点都有对应的同步版本（如 `/parse` 与 `/parse-stream`），确保旧代码不受影响。同步版本保留，新版本逐步迁移到流式。
