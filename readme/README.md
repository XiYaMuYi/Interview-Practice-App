# Readme 导航

## 目录结构

- `01_Core_Constraints/`：核心架构约束、系统架构、技术栈、数据库等最高优先级文档
- `02_Implementation_Guides/`：MVP 计划、前端/分页/UI/流式任务、轻量级监控与调试、Prompt 版本管理、简历工作流重构等实现指导文档
- `03_Agent_Workflows/`：LangGraph、Agent、RAG、ReAct、阅读说明、Prompt 版本监控等工作流与智能体文档

## Claude Code 推荐阅读顺序

### 第一组：先读核心约束
1. `01_Core_Constraints/00_Architecture_Constraints_For_Agent.md`
2. `01_Core_Constraints/01_System_Architecture.md`
3. `01_Core_Constraints/02_Tech_Stack_Design.md`
4. `01_Core_Constraints/03_Database_Schema.md`

### 第二组：再读实现指导
1. `02_Implementation_Guides/05_MVP_Development_Plan.md`
2. `02_Implementation_Guides/07_Frontend_UX_and_Robustness_Strategy.md`
3. `02_Implementation_Guides/08_Frontend_File_Level_Implementation_Plan.md`
4. `02_Implementation_Guides/09_Pagination_Module_Architecture.md`
5. `02_Implementation_Guides/10_Backend_Pagination_Interface_Spec.md`
6. `02_Implementation_Guides/11_UI_Style_and_Motivation_System.md`
7. `02_Implementation_Guides/12_UI_Redesign_Instructions_For_Agent.md`
8. `02_Implementation_Guides/14_Streaming_Task_Pipeline_Architecture.md`
9. `02_Implementation_Guides/15_Prompt_Version_Management_and_Observability.md`
10. `02_Implementation_Guides/16_Resume_Workflow_Refactor_Spec.md`
11. `02_Implementation_Guides/17_Middleware_Architecture_and_Performance.md`
12. `02_Implementation_Guides/18_Streaming_Reality_Check_and_Refactor_Plan.md`
13. `02_Implementation_Guides/Resume_Driven_Interview_Design.md`
14. `02_Implementation_Guides/Resume_Driven_Interview_UI_Design.md`

### 第三组：最后读 Agent / Workflow
1. `03_Agent_Workflows/04_LangGraph_Workflow.md`
2. `03_Agent_Workflows/13_Backend_Agent_RAG_Code_Reading_Guide.md`
3. `03_Agent_Workflows/18_Claude_Code_Auth_Migration_Prompt.md`
4. `03_Agent_Workflows/阅读说明.md`

## 说明

- 这里不建议 Claude Code 先读“代码注释说明文件”，因为那是给人看的辅助信息，不是架构决策源头。
- Claude Code 应先从核心约束与实现指导开始，最后再看 Agent / Workflow 类文档。
- 如果新增文档，请先判断它属于哪个目录层级，再放入对应文件夹。
