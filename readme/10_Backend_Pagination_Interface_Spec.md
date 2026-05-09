# 10_Backend_Pagination_Interface_Spec

## 1. 目标

本项目的后端分页接口不是为某一个页面临时定制，而是面向全站所有列表型数据的统一基础设施。其目标是：

- 所有列表接口返回结构统一
- 所有列表接口分页参数统一
- 所有搜索、筛选、排序接口与分页联动一致
- 前后端共享同一套分页协议
- 未来新增列表页时，不需要重新设计分页返回格式

本规范适用于以下列表类资源：
- Questions 题目列表
- Resumes 简历列表
- Resume_Experiences 简历经历列表
- Study_Records 学习记录列表
- Chat_Histories 对话历史列表
- Review_Lists 待复习列表
- Knowledge_Nodes 知识节点列表
- Question_Knowledge_Nodes 关联列表
- 搜索结果列表
- 统计明细列表

---

## 2. 设计原则

### 2.1 统一性

所有列表接口必须遵守同一个分页参数语义和返回结构。

### 2.2 可预测性

前端只要拿到统一结构，就能渲染分页，不需要为不同接口编写不同分页逻辑。

### 2.3 可组合性

分页必须与以下能力兼容：
- 搜索
- 筛选
- 排序
- 聚合
- 导出
- 刷新

### 2.4 可演进性

未来若从单用户扩展到多用户、从本地部署扩展到云部署，分页协议不应改变。

---

## 3. 统一分页参数规范

### 3.1 推荐参数

所有列表接口建议统一使用：
- `page`：页码，从 1 开始
- `page_size`：每页条数

示例：

```text
GET /api/v1/questions?page=1&page_size=20
```

### 3.2 备用参数

如果个别历史接口已经使用 `offset` / `limit`，可以短期兼容，但新接口必须优先使用 `page` / `page_size`。

### 3.3 参数约束

- `page` 必须 >= 1
- `page_size` 必须 > 0
- `page_size` 必须有上限，例如 100
- 非法参数必须返回明确错误，不允许静默修正成随机值

### 3.4 搜索与筛选参数

分页接口必须兼容通用查询参数，例如：
- `q`：搜索关键词
- `domain_type`
- `question_type`
- `source_type`
- `difficulty_level`
- `status`
- `user_id`
- `resume_id`
- `sort_by`
- `sort_order`

---

## 4. 统一返回结构规范

### 4.1 标准分页响应

所有列表接口统一返回如下结构：

```json
{
  "items": [],
  "total": 123,
  "page": 1,
  "page_size": 20,
  "total_pages": 7
}
```

### 4.2 字段说明

| 字段名 | 类型 | 说明 |
|---|---|---|
| `items` | array | 当前页数据列表 |
| `total` | int | 总条数 |
| `page` | int | 当前页码 |
| `page_size` | int | 每页条数 |
| `total_pages` | int | 总页数 |

### 4.3 推荐扩展字段

根据需要可附加：
- `has_next`
- `has_prev`
- `sort_by`
- `sort_order`
- `query`
- `filters`

但这些扩展字段必须保持可选，不得破坏核心分页结构。

---

## 5. 后端实现建议

### 5.1 统一分页模型

建议后端定义通用泛型分页模型：
- `PaginationParams`
- `PaginationMeta`
- `PaginatedResponse[T]`

### 5.2 分页计算逻辑

分页逻辑必须统一封装在公共函数或 repository 工具中，不允许每个 service 重复写一套 `offset` 计算逻辑。

统一计算方式：
- `offset = (page - 1) * page_size`
- `total_pages = ceil(total / page_size)`

### 5.3 查询分层

推荐结构：
- `api`：接收分页参数、返回分页响应
- `service`：组织查询条件、调用 repository
- `repository`：执行分页查询与总数统计
- `domain`：仅定义数据契约，不关心分页实现细节

---

## 6. 接口规范示例

### 6.1 题目列表

```text
GET /api/v1/questions?page=1&page_size=20&domain_type=RAG&difficulty_level=3
```

返回：

```json
{
  "items": [
    {
      "id": "...",
      "title": "..."
    }
  ],
  "total": 287,
  "page": 1,
  "page_size": 20,
  "total_pages": 15
}
```

### 6.2 简历列表

```text
GET /api/v1/resumes?page=1&page_size=10
```

### 6.3 学习记录列表

```text
GET /api/v1/study/records?page=1&page_size=20&study_type=practice
```

### 6.4 对话历史列表

```text
GET /api/v1/chat/history?page=1&page_size=20&session_id=xxx
```

### 6.5 待复习列表

```text
GET /api/v1/study/review-list?page=1&page_size=20
```

---

## 7. 特殊分页策略

### 7.1 首页概览

首页不需要展示大分页列表。首页只保留少量概览数据，例如：
- 最近 3 条题目
- 最近 3 条简历
- 最近 3 条练习记录

### 7.2 统计页

统计页优先使用聚合接口，不要将原始全量数据全部返回给前端。

### 7.3 详情页

详情页只返回单条完整数据，不做分页。

### 7.4 导出接口

如果未来有导出需求，导出接口不要沿用列表分页返回，而应单独设计任务式导出流程。

---

## 8. 搜索与筛选联动

### 8.1 搜索规则

搜索接口必须支持分页，不允许一次返回全部搜索结果。

### 8.2 筛选规则

筛选条件变化后，页码必须重置为 1。

### 8.3 排序规则

排序变化后，页码必须重置为 1，防止越页后排序语义混乱。

### 8.4 前后端一致性

前端在切换搜索、筛选、排序、页码时，必须和后端参数保持一致，不允许同一个页面出现多套分页语义。

---

## 9. 错误处理规范

### 9.1 参数错误

以下情况必须明确返回 4xx 错误：
- `page` 小于 1
- `page_size` 非法
- 未知筛选字段
- 非法排序字段

### 9.2 空结果

如果分页结果为空，应正常返回：
- `items = []`
- `total = 0`
- `page = 1`
- `total_pages = 0` 或 `1`

但必须保持结构一致，不应返回特殊空结构。

### 9.3 页码越界

如果页码越界，建议：
- 返回空列表并携带总页数
- 或在业务层将页码纠正到最后一页

建议全项目统一一种行为，避免前端判断混乱。

---

## 10. 实现优先级

### 第一优先级
- Questions
- Study_Records
- Chat_Histories
- Resumes

### 第二优先级
- Review_List
- Knowledge_Nodes
- Question_Knowledge_Nodes
- 搜索结果

### 第三优先级
- 统计明细
- 管理后台数据
- 未来扩展资源

---

## 11. 给 Claude Code 的执行原则

当 Claude Code 编写任何列表接口时，必须先确认：
- 是否接入统一分页参数
- 是否返回统一分页结构
- 是否与搜索、筛选、排序联动
- 是否复用了公共分页工具
- 是否避免了全量返回

如果任一答案是否定的，说明该接口不符合本规范。

---

## 12. 最终结论

后端分页接口必须是统一协议，而不是按页面临时拼装。

这个统一协议应该成为项目的基础设施之一，与认证、日志、AI 网关一样，属于横切能力。

任何新的列表接口都应默认继承这套分页规范，而不是重新设计。