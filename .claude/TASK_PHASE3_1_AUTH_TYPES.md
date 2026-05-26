# Phase 3 任务 1/4: Auth 基础类型 + 库改造

## 背景
Phase 2 后端已完成，`/api/v1/auth/me` 返回 `role` 和 `review_status` 字段，`/api/v1/auth/register` 在 pending 状态下返回不同格式（不含 token）。前端需要适配。

## 当前后端返回格式

**/api/v1/auth/register（pending）：**
```json
{
  "user_id": "uuid",
  "username": "xxx",
  "review_status": "pending",
  "message": "账号已创建，等待管理员审核"
}
```

**/api/v1/auth/register（approved，AUTH_ENABLED=false）：**
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 3600,
  "user_id": "uuid",
  "username": "xxx"
}
```

**/api/v1/auth/me：**
```json
{
  "user_id": "uuid",
  "username": "xxx",
  "email": "xxx",
  "is_active": true,
  "role": "user",
  "review_status": "approved",
  "last_login_at": "2026-05-25T..."
}
```

## 需要修改的文件

### 1. `web/src/lib/auth.ts`
- `UserInfo` 接口增加：`role: string`（"user" | "admin"），`review_status: string`（"pending" | "approved" | "rejected" | "disabled"），`last_login_at: string | null`
- `register()` 函数：检查返回是否包含 `review_status === "pending"`，如果是则返回特殊结构（不含 token），调用方可据此判断
- 新增类型 `RegisterPendingResult`：`{ review_status: "pending", user_id: string, username: string, message: string }`
- `register()` 返回值改为联合类型：`UserInfo | RegisterPendingResult`

### 2. `web/src/contexts/AuthContext.tsx`
- `register()` 回调：如果返回 pending 结果，**不**调用 `setUser`（因为没有 token），而是让调用方处理
- 新增状态：`reviewStatus: "pending" | "approved" | "rejected" | "disabled" | null`
- 从 `/me` 响应中解析 `role` 和 `review_status` 存入 state

## 规则
- 不要修改不相关的代码
- 保持现有 auth_disabled 行为不变
- TypeScript 类型要准确，不要用 `any`
- 修改完成后不要重启 Docker 或 dev server，只做代码改动
