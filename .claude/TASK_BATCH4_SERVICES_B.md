# Batch 4: Service 层改造（study + chat + exam）

## 必读
- `backend/app/infra/data_isolation.py`
- `backend/app/api/deps.py`
- `backend/app/services/study_service.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/exam_service.py`

## 任务

### 任务 1: study_service.py

文件：`backend/app/services/study_service.py`

1. import 头部添加：
```python
from app.infra.data_isolation import UserContext, ensure_owned_by
```

2. 所有创建学习记录的方法（如 `create_study_record` / `record_study`）：
   - 添加参数 `user_ctx: UserContext`
   - 创建时设置 `user_id=user_ctx.user_id`

3. 所有查询方法（如 `list_study_records` / `get_study_stats`）：
   - 添加参数 `user_ctx: UserContext`
   - 查询加过滤 `{"user_id": user_ctx.user_id}`

4. 管理豁免：is_admin=True 时不过滤

---

### 任务 2: chat_service.py

文件：`backend/app/services/chat_service.py`

1. import 头部添加：
```python
from app.infra.data_isolation import UserContext, ensure_owned_by
```

2. 创建对话记录：
   - 添加参数 `user_ctx: UserContext`
   - 创建时设置 `user_id=user_ctx.user_id`

3. 查询对话历史（如 `get_chat_history` / `list_sessions`）：
   - 添加参数 `user_ctx: UserContext`
   - 查询加过滤 `{"user_id": user_ctx.user_id, "session_id": session_id}`

4. 确保 session_id 也结合 user_id 做隔离（防止 session 碰撞）

---

### 任务 3: exam_service.py

文件：`backend/app/services/exam_service.py`

1. import 头部添加：
```python
from app.infra.data_isolation import UserContext, ensure_owned_by
```

2. 创建考试会话：
   - 添加参数 `user_ctx: UserContext`
   - 创建 ExamSession 时设置 `user_id=user_ctx.user_id`

3. 创建答卷（ExamAnswer）：
   - 添加参数 `user_ctx: UserContext`
   - 创建 ExamAnswer 时设置 `user_id=user_ctx.user_id`

4. 查询考试/答卷：
   - 添加参数 `user_ctx: UserContext`
   - 查询加过滤 `{"user_id": user_ctx.user_id}`

5. 校验考试归属权：用户只能操作自己的考试会话

## 完成标准
- study_service, chat_service, exam_service 都已加入 user_ctx
- 所有创建/查询都有 user_id 过滤
- 不需要 docker 重建
