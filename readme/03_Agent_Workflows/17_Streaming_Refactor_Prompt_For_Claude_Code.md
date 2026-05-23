# Claude Code 流式重构提示词

请先阅读以下文档，再开始修改代码：

1. `readme/README.md`
2. `readme/01_Core_Constraints/00_Architecture_Constraints_For_Agent.md`
3. `readme/01_Core_Constraints/01_System_Architecture.md`
4. `readme/02_Implementation_Guides/14_Streaming_Task_Pipeline_Architecture.md`
5. `readme/02_Implementation_Guides/16_Resume_Workflow_Refactor_Spec.md`
6. `readme/02_Implementation_Guides/17_Middleware_Architecture_and_Performance.md`
7. `readme/02_Implementation_Guides/18_Streaming_Reality_Check_and_Refactor_Plan.md`
8. `readme/03_Agent_Workflows/13_Backend_Agent_RAG_Code_Reading_Guide.md`

---

## 你的任务目标

请把当前项目里所有“AI 生成内容”的输出方式梳理清楚，并优先把最有用户感知的 AI 生成接口改造成真正的 token 级流式输出，而不是“先生成完整结果再分段返回”的伪流式。

当前项目已经有很多 SSE / 任务流 / 进度流，但大部分 AI 内容输出仍然是一次性生成后再返回。你要把这件事改真实。

---

## 你要先识别的三类接口

### 1. 真流式
指底层真正使用 `llm_gateway.stream_chat(...)`，模型 token 是边生成边输出的。

### 2. 伪流式
指接口表面上用 SSE / StreamingResponse，但底层还是先 `chat(...)` 或 `chat_json(...)` 拿完整结果，再把完整结果包装成流式事件。

### 3. 阶段流式
指接口只流式输出任务阶段、进度、chunk、保存状态，但模型本身不是 token 级流式。

---

## 你必须优先改造的功能点

### 第一优先级
1. `AIService.explain_question_stream`
2. `AIService.handle_interview_turn_stream`
3. `AIService.generate_review_summary_stream`

这些接口最值得先改成 token 级流式，因为它们最能体现“AI 正在实时思考”的效果。

### 第二优先级
4. `ResumeService.generate_questions_from_resume_stream`
5. `ResumeService.regenerate_questions_stream`
6. `ImportService.import_text_stream`

这些接口属于批量生成或长任务生成，适合逐段/逐题流式展示。

### 第三优先级
7. `AIService.evaluate_answer_stream`
8. `ImportService._extract_questions`
9. `ResumeService.parse_resume_stream`

这些接口不一定适合纯 token 流式，但可以改成更细粒度的阶段流式或增量结果流式。

---

## 具体改造要求

### 1. 为 LLMGateway 补真正的流式封装
请检查 `backend/app/infra/llm/gateway.py`，如果还没有统一封装，新增：
- `stream_chat_with_prompt(...)`
- 必要时新增 `stream_json_with_prompt(...)`

要求：
- 允许 prompt registry 参与
- 允许记录 prompt_version
- 允许记录 LLM 调用日志
- 允许继续保留 cache / audit / event 发布能力

### 2. 把最关键的生成接口改成 token 事件输出
对于讲解、追问、总结等接口：
- 不能再只等完整文本生成完
- 要边生成边通过 SSE 输出 token
- 前端要能逐步显示内容

建议统一 SSE 事件格式：
- `progress`
- `token`
- `result`
- `done`
- `error`

### 3. 保留任务状态与阶段流
即使改成 token 流式，也不要丢掉：
- task_id
- progress
- current_phase
- chunk 信息
- 保存状态
- done / error

也就是说，token 流式要叠加在现有任务流式之上，而不是替换掉它。

### 4. 让前端真的能看出“变快/更实时”
不要只把接口名改成 stream，结果还是一次性返回。
要让前端能看到：
- 打字机效果
- 逐 token 增量
- 中间阶段进度
- 生成中提示

### 5. 对 JSON 类接口做现实处理
对于 `evaluate_answer_stream` 这类结构化结果接口：
- 不强求纯 token 流式 JSON
- 可以先流式输出评价过程提示
- 最后一次性输出结构化 JSON

### 6. 保持本地可运行与降级能力
如果某个接口暂时不适合真流式：
- 允许降级为阶段流式
- 但必须明确标记它不是 token 级真流式
- 不要伪装成真流式

---

## 你最终需要输出的内容

请在完成修改后，输出：
1. 哪些接口已经变成真流式
2. 哪些接口仍然是阶段流式或伪流式
3. 哪些接口最值得优先改造，并为什么
4. 你新增了哪些 LLM 流式封装
5. 哪些 SSE 事件格式发生了变化
6. 哪些地方仍保留了任务流 / cache / audit
7. 哪些地方只是预留或降级，没有强行做 token 流式

---

## 最终要求

请优先把用户最能感知的 AI 生成内容改成真正的 token 级流式，而不是表面上 stream、实际上还是一次性返回。

请开始阅读文档并改代码。