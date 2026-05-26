# Batch 5: Routes 改造 + Docker 重建

## 必读
- `backend/app/api/deps.py` — get_user_context
- `backend/app/infra/data_isolation.py`
- `backend/app/api/v1/routes/import_routes.py`
- `backend/app/api/v1/routes/resume_routes.py`
- `backend/app/api/v1/routes/question_routes.py`
- `backend/app/api/v1/routes/study_routes.py`
- `backend/app/api/v1/routes/chat_routes.py`
- `backend/app/api/v1/routes/exam_routes.py`
- `backend/app/api/v1/register_routes.py` — 路由注册

## 任务

### 路由改造原则
- 每个私有数据端点添加 `user_ctx: UserContext = Depends(get_user_context)` 参数
- 将 user_ctx 传给对应的 service 方法
- 公开数据端点（公共题库列表）不需要 user_ctx

---

### 1. import_routes.py

- 文件上传/列表/删除端点 → 添加 `user_ctx: UserContext = Depends(get_user_context)`
- 调用 service 时传入 user_ctx

### 2. resume_routes.py

- 简历列表/创建/详情/删除 → 添加 user_ctx 参数
- 传给 service

### 3. question_routes.py

- 题目列表（公开）→ 添加 user_ctx（支持公共+私有混合查询）
- 题目创建 → 添加 user_ctx
- 题目详情/删除 → 添加 user_ctx + 归属权校验

### 4. study_routes.py

- 学习记录查询/创建 → 添加 user_ctx

### 5. chat_routes.py

- 对话历史/创建 → 添加 user_ctx
- 确保 session_id 和 user_id 双重隔离

### 6. exam_routes.py

- 考试创建/列表/提交/答卷 → 添加 user_ctx
- 考试详情/批改 → 添加 user_ctx + 归属权校验

### 7. register_routes.py

- 确认所有 route 模块都已注册
- 如有新增路由需在此注册

---

### 8. Docker 重建

完成所有代码改动后，执行：

```bash
docker-compose down
docker-compose up -d --build
```

然后验证后端是否正常启动：
```bash
docker logs interview_backend --tail 30
```

确认没有启动错误，Alembic 迁移成功。

## 完成标准
- 所有私有数据端点都有 user_ctx 注入
- 公开端点不需要 user_ctx 保持可用
- Docker 重建成功，后端正常启动
- Alembic 迁移已应用
