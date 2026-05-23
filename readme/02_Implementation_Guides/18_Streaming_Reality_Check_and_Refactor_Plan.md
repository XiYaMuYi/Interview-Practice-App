# 18_Streaming_Reality_Check_and_Refactor_Plan

## 1. 目的

本文件用于回答一个非常具体的问题：

> 当前项目里，哪些 AI 生成接口已经是真流式，哪些只是伪流式，哪些最值得优先改造成 token 级流式输出？

这里的“真流式”指：
- 模型生成内容是分片/增量输出的
- 前端可以边生成边看到内容
- 后端不需要等完整结果生成完才返回

这里的“伪流式”指：
- 接口虽然使用了 `StreamingResponse` 或 SSE
- 但底层仍然是先一次性调用模型拿完整结果
- 然后再把完整结果包装成 SSE 分段输出

---

## 2. 当前代码现状结论

### 2.1 已经是真流式的部分

#### A. 任务进度流式
这些接口的流式主要用于“进度展示”，不是 token 级模型输出，但属于真实的 SSE 流：

- `backend/app/api/v1/routes/import_routes.py`
  - `/text-stream`
  - `/text-stream-async`
- `backend/app/api/v1/routes/resume_routes.py`
  - `/parse-stream`
  - `/parse-stream-async`
  - `/regenerate-questions`
  - `/generate-questions-stream`
- `backend/app/api/v1/routes/task_events.py`
  - `/{task_id}/events`

这些接口会持续向前端发出：
- progress
- chunk_saved
- question_saved
- error
- done

它们是真正的“任务流式”，但**不是 token 级模型输出流式**。

#### B. LLM 层已经支持真流式
`backend/app/infra/llm/gateway.py` 中已经存在：
- `stream_chat(...)`

底层 provider 也有：
- `stream_chat_completion(...)`

所以从基础设施能力上看，项目已经具备真流式模型输出能力。

---

### 2.2 目前仍属于伪流式的部分

以下功能虽然对外表现为流式，但底层仍是“先完整生成，再输出完整结果”：

#### A. 题目讲解
- `backend/app/services/ai_service.py`
  - `explain_question_stream(...)`

现状：
- 先调用 `self.llm.chat(...)`
- 拿到完整解释文本
- 再通过 SSE 一次性发出 `content`

这属于典型伪流式。

#### B. 回答评价
- `backend/app/services/ai_service.py`
  - `evaluate_answer_stream(...)`

现状：
- 先调用 `chat_json_with_prompt(...)`
- 拿到完整 JSON
- 再通过 SSE 发出 `evaluation` / `result`

这不是 token 级流式。

#### C. 单轮面试追问
- `backend/app/services/ai_service.py`
  - `handle_interview_turn_stream(...)`

现状：
- 先完成评分
- 再生成 follow-up 或 summary
- 最后统一发 SSE

这也是“事件流式”，不是 token 级生成流式。

#### D. 复盘总结
- `backend/app/services/ai_service.py`
  - `generate_review_summary_stream(...)`

如果它内部仍然是先完整拿到总结再输出，那也属于伪流式或阶段流式。

---

### 2.3 最值得优先改成 token 流式的部分

以下接口最值得先改，因为它们最能让用户明显感知“AI 在实时生成”：

#### 优先级 1：题目讲解
- `explain_question_stream(...)`

原因：
- 用户最容易感知解释内容的逐字输出
- 最适合作为前端“打字机效果”
- 改成 token 流式后，体验提升最明显

#### 优先级 2：面试追问生成
- `generate_followup(...)`
- `handle_interview_turn_stream(...)`

原因：
- 追问文本通常较短，但用户希望立刻看到生成过程
- 可以实现 token 流式 + SSE 增量输出
- 对“智能面试官”感知提升很明显

#### 优先级 3：复盘总结
- `generate_review_summary_stream(...)`

原因：
- 内容通常较长
- 很适合流式展示
- 能让“总结生成中”的过程更真实

#### 优先级 4：题目生成 / 简历驱动出题
- `generate_questions_from_resume_stream(...)`
- `regenerate_questions_stream(...)`

原因：
- 这类任务本身就是批量生成
- 可以先保留阶段流式，再把“单题生成”部分升级成 token 流式

---

## 3. 为什么当前很多地方不是 token 流式

当前项目的主问题不是“没有 stream 接口”，而是：

1. 业务层多数调用的是 `chat(...)` 或 `chat_json(...)`
2. 这些方法天然是“等待完整结果后返回”
3. SSE 只是把完整结果拆成阶段事件发送
4. 还没有把 `llm_gateway.stream_chat(...)` 真正贯穿到业务层

因此当前项目更像：
- 任务流式
- 阶段流式
- 结果流式包装

而不是：
- token 级实时输出

---

## 4. 建议的改造顺序

### 第一阶段：先改最有感知的 3 个接口
1. `explain_question_stream`
2. `handle_interview_turn_stream`
3. `generate_review_summary_stream`

目标：
- 前端立刻看到 token 级生成效果
- 让“AI 真的在思考”的感觉先出现

### 第二阶段：再改出题链路
1. `generate_questions_from_resume_stream`
2. `regenerate_questions_stream`
3. `import_text_stream`

目标：
- 长文本生成更顺滑
- 批量题目生成时可逐题展示

### 第三阶段：最后补纯 JSON 类接口
- `evaluate_answer_stream`
- `classify_question`
- `resume_parsing`

这类接口不一定适合严格 token 流式，但可以做：
- 先流式展示推理阶段
- 再在最后输出结构化 JSON

---

## 5. 技术改造建议

### 5.1 新增统一的流式封装
建议在 `LLMGateway` 或 service 层新增：
- `stream_chat_with_prompt(...)`
- `stream_json_with_prompt(...)`

其中：
- `stream_chat_with_prompt(...)` 负责 token 级文本流
- `stream_json_with_prompt(...)` 负责先流式输出中间文字，再在最后拼 JSON

### 5.2 前端 SSE 事件建议
建议统一使用这些事件：
- `progress`
- `token`
- `chunk_saved`
- `result`
- `done`
- `error`

其中：
- `token` 事件专门用于增量文本
- `progress` 用于阶段状态
- `result` 用于最终结构化结果

### 5.3 缓存策略建议
流式接口不一定都适合缓存整段结果。
建议：
- 缓存 prompt 级最终结果
- token 流过程不缓存
- 对高频短文本可以缓存最终文本
- 对长文本生成主要缓存最终答案摘要或结构化结果

---

## 6. 判断标准

### 真流式
满足以下任一条件：
- 后端使用 `llm_gateway.stream_chat(...)`
- 前端能逐 token 接收内容
- 用户可以在生成过程中看到逐步变化

### 伪流式
满足以下任一条件：
- 先 `chat(...)` / `chat_json(...)` 拿完整结果
- 再用 SSE 一次性或分阶段发送
- 前端无法真正看到 token 增量

### 阶段流式
满足以下任一条件：
- 有 SSE
- 有 progress / chunk 事件
- 但模型输出本身不是 token 级

当前项目里，阶段流式已经很多，但 token 流式还不够。

---

## 7. 给 Claude Code 的直接改造目标

在后续重构中，Claude Code 应优先：

1. ~~把 `explain_question_stream` 改成 token 流式~~ — **已完成**
2. ~~把 `handle_interview_turn_stream` 中的总结/追问改成 token 流式~~ — **已完成**
3. ~~把 `generate_review_summary_stream` 改成 token 流式~~ — **已完成**
4. ~~为 `LLMGateway` 新增统一的流式 Prompt 调用方法~~ — **已有 `stream_chat_with_prompt()`**
5. 让前端 SSE 可以识别 `token` 和 `content` 事件
6. ~~保持现有阶段事件和任务状态不丢失~~ — **已完成**

---

## 8. 最终结论

当前项目已经具备”流式任务”的基础，但真正能让用户感知到 AI 实时生成的 token 级流式，还主要集中在讲解、追问、复盘这几类接口。

所以最值得先改的是：
- `explain_question_stream`
- `handle_interview_turn_stream`
- `generate_review_summary_stream`

这三类接口改完后，整体体验提升会最明显。

---

## 9. 流式改造完成总结（2026-05-23）

### 9.1 已变成真 token 级流式的接口

| 接口 | Service 方法 | LLM 调用 | 事件类型 |
|------|-------------|----------|----------|
| `POST /ai/explain-stream` | `explain_question_stream` | `stream_chat()` | `token` + `content`(~50字符) + `progress` + `done` |
| `POST /ai/interview/turn-stream` | `handle_interview_turn_stream` | `stream_chat_with_prompt()`(summary) | `token` + `content` + `evaluation` + `followup/summary` + `done` |
| `POST /study/review-stream` | `generate_review_summary_stream` | `stream_chat_with_prompt()` | `token` + `content`(~50字符) + `progress` + `done` |

### 9.2 仍是阶段流式（非 token 级）的接口

| 接口 | Service 方法 | 原因 |
|------|-------------|------|
| `POST /ai/evaluate-stream` | `evaluate_answer_stream` | JSON 结构化输出，不适合 token 级流式 |
| `POST /ai/graph/*-stream` | LangGraph 工作流 | 节点级事件流式，非 token 级 |
| `POST /ai/followup` | `generate_followup` | 同步 JSON 调用 |

### 9.3 关键修复

1. **TaskManager `publish_task_event()`**：新增方法，将 generator yield 的事件同步推送给 SSE 订阅者队列，解决了 POST 后台任务的事件无法通过 GET `/tasks/{task_id}/events` 端点推送的根本问题
2. **Content 累积事件**：每累积 ~50 字符 emit 一次 `content` 事件，前端可以拿到完整累积文本，避免只收到零散 token
3. **Event type 字段**：所有事件 dict 增加 `event_type` 字段，与 `sse_event_stream()` 的解析逻辑兼容

### 9.4 事件发布双通道

改造后，每个 SSE 事件通过两个通道发出：
- **直接 yield**：POST 端点的 `StreamingResponse` 直接接收
- **publish_task_event()**：通过 TaskManager 类级 `_subscribers` 字典推送给 GET `/tasks/{task_id}/events` 端点

两个通道共享同一个订阅者池，确保无论前端采用哪种消费模式都能收到事件。
