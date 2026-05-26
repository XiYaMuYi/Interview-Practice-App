# Batch 3: Service 层改造（import + resume + question）

## 必读
- `backend/app/infra/data_isolation.py` — Batch 2 新增的 UserContext
- `backend/app/api/deps.py` — Batch 2 新增的 get_user_context
- `backend/app/services/import_service.py`
- `backend/app/services/resume_service.py`
- `backend/app/services/question_service.py`

## 原则
- 每个 service 方法如果涉及用户私有数据，需加 `user_ctx: UserContext` 参数
- 创建时写入 `user_id`
- 查询时按 user_id 过滤
- 删除/更新时校验归属权

---

## 任务 1: import_service.py

文件：`backend/app/services/import_service.py`

### 修改点

1. **import 头部添加**：
```python
from app.infra.data_isolation import UserContext, ensure_owned_by
```

2. **upload_file / create_file 方法**：
   - 添加参数 `user_ctx: UserContext`
   - 创建 File 对象时设置 `user_id=user_ctx.user_id`

3. **list_files 方法**：
   - 添加参数 `user_ctx: UserContext`
   - 查询时加过滤：`{"user_id": user_ctx.user_id}`（非管理员且非匿名）

4. **get_file 方法**：
   - 添加参数 `user_ctx: UserContext`
   - 获取文件后调用 `ensure_owned_by(user_ctx, file.user_id, "file")` 校验归属权

---

## 任务 2: resume_service.py

文件：`backend/app/services/resume_service.py`

### 修改点

1. **import 头部添加**：
```python
from app.infra.data_isolation import UserContext, ensure_owned_by
```

2. **创建简历方法**（如 `create_resume` / `upload_resume`）：
   - 添加参数 `user_ctx: UserContext`
   - 创建 Resume 时设置 `user_id=user_ctx.user_id`

3. **list_resumes 方法**：
   - 添加参数 `user_ctx: UserContext`
   - 查询加过滤 `{"user_id": user_ctx.user_id}`

4. **get_resume 方法**：
   - 添加参数 `user_ctx: UserContext`
   - 获取后调用 `ensure_owned_by(user_ctx, resume.user_id, "resume")`

---

## 任务 3: question_service.py

文件：`backend/app/services/question_service.py`

### 修改点

1. **import 头部添加**：
```python
from app.infra.data_isolation import UserContext, ensure_owned_by, check_resource_ownership
```

2. **list_questions / search_questions**：
   - 添加参数 `user_ctx: UserContext`
   - 过滤逻辑：
     - 管理员 → 不过滤（看全部）
     - 匿名用户 → 只看 `user_id IS NULL`（公共题目）
     - 已登录 → 看 `user_id IS NULL`（公共）或 `user_id = current_user`（自己的）

3. **create_question**：
   - 添加参数 `user_ctx: UserContext`
   - 如果 user_ctx 非匿名且非管理员，设置 `user_id=user_ctx.user_id`
   - 管理员创建时 user_id 可为 NULL（公共题目）

4. **get_question**：
   - 添加参数 `user_ctx: UserContext`
   - 管理员可看所有题目
   - 匿名用户只能看 user_id=NULL 的题目
   - 已登录用户只能看自己的或公共的题目

---

## 完成标准
- import_service, resume_service, question_service 都已加入 user_ctx 参数
- 所有创建操作写入 user_id
- 所有查询操作按 user_id 过滤
- 不需要 docker 重建
