# 15_Prompt_Version_Management_and_Observability

## 1. 目标

本文件是给自动编码 Agent、Claude Code、Open Cloud 以及后续所有会修改代码的智能体看的。

它的核心目标不是给人类做概念科普，而是告诉智能体：
- 代码里的 Prompt 不是随手写的字符串
- 所有 Prompt 都需要版本化管理
- 每次修改 Prompt 都要能回放、比较和追踪效果
- 修改代码时，必须知道当前使用的是哪个 Prompt 版本

这个文件属于 Agent / Workflow 类文档，而不是实现细节说明文档。

---

## 2. 为什么要做 Prompt 版本管理

### 2.1 Prompt 本身会持续变化

在本项目里，Prompt 会用于：
- 简历解析
- 问题分类
- 面试题生成
- 答案评价
- 追问生成
- 知识点提取
- 讲解生成
- 结构化输出

这些 Prompt 不是一次写死就结束，而是会随着：
- 模型变化
- 输出结构变化
- 业务策略变化
- 用户反馈变化
- 解析失败率变化
持续调整。

### 2.2 没有版本管理就没法排查问题

如果没有版本管理，就会出现：
- 不知道当前代码里是哪一个 Prompt 在生效
- 不知道某次结果变好是模型改进还是 Prompt 改进
- 不知道某次结果变差是数据问题还是 Prompt 退化
- 不知道旧结果是否还能复现

### 2.3 版本管理本身也是轻量监控

Prompt 版本管理不只是为了“保存历史”，它还承担一个很重要的作用：

> 帮助我们低成本判断当前 AI 行为是否退化、是否超时、是否解析失败、是否生成偏差。

它是一种轻量、可实施、适合个人开发者的监控方式。

---

## 3. 版本管理对象

### 3.1 Prompt 模板

每个 Prompt 模板都应该具备：
- `prompt_key`
- `prompt_version`
- `description`
- `applies_to`
- `model_hints`
- `created_at`
- `updated_at`
- `is_active`

### 3.2 AI 运行结果

每次调用模型时都应该记录：
- `task_id`
- `session_id`
- `prompt_key`
- `prompt_version`
- `model_version`
- `duration_ms`
- `status`
- `error_message`
- `response_preview`

### 3.3 结果产物

如果 Prompt 产出被写入数据库，也要能知道：
- 这条题目 / 讲解 / 追问来自哪个 Prompt 版本
- 这条结果是否经过后续修订
- 这条结果是否为最终版

---

## 4. 推荐的 Prompt 管理方式

### 4.1 统一注册中心

所有 Prompt 都应该通过统一注册中心管理，而不是散落在节点函数、service 函数或路由里。

建议继续使用：
- `PromptRegistry`

### 4.2 模板与版本分离

同一个 `prompt_key` 可以存在多个版本，例如：
- `answer_evaluation@1.0`
- `answer_evaluation@1.1`
- `answer_evaluation@2.0`

这样方便：
- 对比效果
- 灰度发布
- 回滚旧版本

### 4.3 版本切换规则

建议遵循：
- 小修小改：只升补丁版本
- 结构变化：升次版本
- 输出 schema 明显变化：升主版本

---

## 5. 结果评估指标

Prompt 版本对比时，建议关注以下轻量指标：
- 结构化输出成功率
- JSON 解析成功率
- 超时率
- 重试率
- 平均耗时
- 用户后续是否继续追问
- 生成结果是否被人工修改
- 评价结果是否稳定

在模拟面试、题目生成、讲解输出等场景，还可以关注：
- 题目命中率
- 通过率
- 复习后提升率
- 追问命中率
- 用户满意度

---

## 6. 推荐的数据字段

### 6.1 PromptTemplate

建议至少包含：
- `key`
- `version`
- `system_template`
- `description`
- `model_hints`
- `created_at`
- `updated_at`
- `is_active`

### 6.2 AI 调用日志

建议至少包含：
- `id`
- `task_id`
- `session_id`
- `prompt_key`
- `prompt_version`
- `model_name`
- `duration_ms`
- `status`
- `error_code`
- `error_message`
- `created_at`

### 6.3 结果记录

建议在题目、讲解、追问、复习记录等业务表中保存：
- `model_version`
- `prompt_key`
- `prompt_version`
- `state_version`

---

## 7. 给 Claude Code 的执行要求

在修改任何 LLM 相关代码时，Claude Code 必须：
- 明确当前使用的 `prompt_key`
- 明确当前使用的 `prompt_version`
- 如果修改了 prompt，必须同步更新版本号
- 如果新增 prompt，必须注册到 `PromptRegistry`
- 如果输出结构变化，必须同步更新相关 schema、日志与说明文档

---

## 8. 与其他文档的关系

本文件与以下文档配套：
- `01_Core_Constraints/00_Architecture_Constraints_For_Agent.md`：定义提示词必须版本管理的红线
- `02_Implementation_Guides/14_Streaming_Task_Pipeline_Architecture.md`：定义长任务流式执行
- `03_Agent_Workflows/13_Backend_Agent_RAG_Code_Reading_Guide.md`：定义 Agent / RAG 阅读路线
- `03_Agent_Workflows/04_LangGraph_Workflow.md`：定义工作流边界与 ReAct 适用范围

---

## 9. 最终结论

Prompt 版本管理不是额外装饰，而是 AI 项目可维护性的基础能力。

如果没有版本管理，就很难比较效果、回放结果、定位退化点，也很难让 Claude Code 或 Open Cloud 快速排障。

因此：
- Prompt 要版本化
- 调用要可追踪
- 结果要可回放
- 修改要可比较
