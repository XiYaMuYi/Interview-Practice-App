# Phase 2: 数据归属隔离 (Data Ownership & Multi-Tenant Isolation)

## 背景

Phase 1 已完成认证体系（JWT、审核流、User 模型角色）。Phase 2 要在所有私有数据接口上强制 `user_id` 隔离，公共数据保持共享。

## 必须先读的文档

1. `readme/01_Core_Constraints/00_Architecture_Constraints_For_Agent.md`
2. `readme/01_Core_Constraints/03_Database_Schema.md`
3. `readme/02_Implementation_Guides/19_Auth_and_MultiTenant_Architecture_Draft.md`
4. `backend/app/domain/models/__init__.py` — 所有现有 SQLModel 实体
5. `backend/app/domain/models/user.py` — Phase 1 新增 User/ReviewRecord
6. `backend/app/api/deps.py` — Phase 1 新增的认证依赖
7. `backend/app/services/` — 所有现有 service 文件

## 数据域分类

### 公共共享域（不需要 user_id 隔离）
- `tags` / `question_tags` — 全局标签
- `knowledge_nodes` / `question_knowledge_nodes` — 知识图谱
- `question_embeddings` — 向量数据（跟随 question）
- `prompt_versions` — 提示词模板
- `event_audit_logs` / `llm_call_logs` — 系统审计
- `tasks` — 后台任务

### 私有用户域（必须 user_id 隔离）
| 表 | 已有 user_id? | 说明 |
|---|---|---|
| `files` | ❌ **缺** | 用户上传的文件 |
| `resumes` | ✅ | 用户简历 |
| `resume_experiences` | 通过 resume_id 间接归属 | 简历经历 |
| `questions` | ✅ | 题目（可公共可私有） |
| `study_records` | ✅ | 学习记录 |
| `chat_histories` | ✅ | 对话历史 |
| `learning_profiles` | ✅ | 学习画像 |
| `exam_sessions` | ✅ | 考试会话 |
| `exam_answers` | ❌ **缺** | 考试答卷 |

## 子任务

### 任务 1：补全缺失的 user_id 字段

#### 1a. File 模型加 user_id

文件：`backend/app/domain/models/__init__.py`
- `File` 类添加：`user_id: str | None = Field(default=None, max_length=255)`

#### 1b. ExamAnswer 模型加 user_id

文件：`backend/app/domain/models/__init__.py`
- `ExamAnswer` 类添加：`user_id: str | None = Field(default=None, max_length=255)`

#### 1c. Alembic 迁移

新建：`backend/alembic/versions/g1h2i3j4k5l6_add_user_id_to_files_exam_answers.py`
- `down_revision = "f1a2b3c4d5e6"`
- 幂等：检查列是否存在再添加
- `files` 加 `user_id VARCHAR(255)` + 索引 `ix_files_user_id`
- `exam_answers` 加 `user_id VARCHAR(255)` + 索引 `ix_exam_answers_user_id`
- 已有行 user_id 保持 NULL（公共/历史数据）
- downgrade 可回退

### 任务 2：创建 user_context 依赖（数据隔离核心）

文件：`backend/app/api/deps.py`

新增：
```python
from dataclasses import dataclass

@dataclass
class UserContext:
    """用户上下文，用于数据隔离查询。"""
    user_id: str | None
    is_anonymous: bool

async def get_user_context(
    current_user: User | None = Depends(get_current_user),
) -> UserContext:
    """返回当前请求的用户上下文。
    
    - AUTH_ENABLED=False 时：返回匿名上下文
    - AUTH_ENABLED=True 且未登录：返回匿名上下文（不强制 401，让各路由自行决定）
    - 已登录：返回 UserContext(user_id=str(user.id), is_anonymous=False)
    """
```

### 任务 3：创建 data_isolation 工具模块

新建：`backend/app/infra/data_isolation.py`

```python
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class UserFilterContext:
    user_id: Optional[str]
    is_anonymous: bool
    is_admin: bool = False

def apply_user_filter(
    filters: Dict[str, Any],
    ctx: UserFilterContext,
    table_has_user_id: bool = True,
    allow_public: bool = False,
) -> Dict[str, Any]:
    """将 user_id 注入查询过滤器。
    
    Args:
        filters: 现有过滤条件
        ctx: 用户上下文
        table_has_user_id: 表是否有 user_id 字段
        allow_public: 是否允许看到公共数据(user_id=NULL)
    
    Returns:
        更新后的过滤器字典
    
    逻辑：
    - 匿名且非管理员 → 只看公共数据 (user_id IS NULL)
    - 已登录用户 → 看自己的 + 公共的 (user_id = current OR user_id IS NULL)
    - 管理员 → 看所有数据
    """
    if ctx.is_admin:
        # 管理员可看全部，不额外加过滤
        return filters
    
    if ctx.is_anonymous:
        # 匿名用户只看公共数据
        if allow_public and table_has_user_id:
            # 需要在 repository 层用 OR 条件处理
            filters["__user_filter_mode"] = "public_only"
        return filters
    
    # 已登录用户：自己的 + 公共的
    if table_has_user_id:
        filters["__user_filter_mode"] = "owned_or_public"
        filters["__user_id"] = ctx.user_id
    
    return filters

def check_resource_ownership(
    ctx: UserFilterContext,
    resource_user_id: str | None,
    resource_name: str = "resource",
) -> bool:
    """检查资源归属。返回 True 表示可访问，False 表示无权。"""
    if ctx.is_admin:
        return True
    if ctx.is_anonymous:
        # 匿名只能访问公共资源
        return resource_user_id is None
    # 已登录：自己的或公共的
    return resource_user_id is None or resource_user_id == ctx.user_id
```

### 任务 4：改造所有私有数据 Service

对以下 service，在创建/查询/更新/删除操作中注入 user_id 过滤：

#### 4a. import_service.py
- `upload_file()` / 文件创建 → 写入 `user_id`
- `list_files()` → 按 `user_id` 过滤
- `get_file()` → 检查归属权

#### 4b. resume_service.py
- 已有 `user_id` 字段 → 确保所有查询按 `user_id` 过滤
- 创建时写入 `user_id`

#### 4c. question_service.py
- 公共题库（user_id=NULL）对所有用户可见
- 私有题目（user_id 有值）仅创建者可见
- 管理员可看全部
- `list_questions()` / `search_questions()` → 加入 user_filter

#### 4d. study_service.py
- 所有查询按 `user_id` 过滤
- 创建时写入 `user_id`

#### 4e. chat_service.py
- 对话历史按 `user_id` + `session_id` 过滤
- 创建时写入 `user_id`

#### 4f. exam_service.py
- exam_sessions / exam_answers 按 `user_id` 过滤
- 创建时写入 `user_id`

### 任务 5：改造所有私有数据 Routes

为以下路由文件添加 `user_ctx = await get_user_context(...)`，传入 service：

- `backend/app/api/v1/routes/import_routes.py`
- `backend/app/api/v1/routes/resume_routes.py`
- `backend/app/api/v1/routes/question_routes.py`
- `backend/app/api/v1/routes/study_routes.py`
- `backend/app/api/v1/routes/chat_routes.py`
- `backend/app/api/v1/routes/exam_routes.py`
- `backend/app/api/v1/routes/ai_routes.py`（如有需要）

### 任务 6：注册路由

确保所有改动在 `backend/app/api/v1/register_routes.py` 中已正确注册。

## 约束

1. **严格分层**：api → services → domain/infra，禁止跨层
2. **幂等迁移**：必须检查列/索引是否存在
3. **不破坏公共题库**：user_id=NULL 的题目对所有用户可见
4. **不改变 Phase 1 逻辑**：认证/审核流程保持不动
5. **匿名处理**：AUTH_ENABLED=False 时匿名用户的 user_id=None，查询公共数据正常
6. **管理员特权**：admin 可看所有数据
7. **向后兼容**：已有 user_id=NULL 数据视为公共/遗留

## 完成标准

- [ ] File 和 ExamAnswer 模型有 user_id 字段
- [ ] Alembic 迁移可成功 apply
- [ ] 所有私有数据创建时自动写入 user_id
- [ ] 所有私有数据查询按 user_id 过滤
- [ ] 匿名用户访问私有数据 → 返回该用户可访问的部分（公共数据）或 401
- [ ] 用户 A 不能访问用户 B 的私有数据
- [ ] 管理员可查看所有数据
- [ ] 公共题库对所有用户可见
- [ ] 所有路由已注册
