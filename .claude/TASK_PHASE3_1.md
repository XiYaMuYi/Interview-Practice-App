# Phase 3 Task 1/4: Auth 基础类型 + register pending 处理

## 目标
改造 `web/src/lib/auth.ts` 和 `web/src/contexts/AuthContext.tsx`，支持后端新增的 `role`、`review_status` 字段，以及注册后 pending 审核的分支。

## 改动 1: `web/src/lib/auth.ts`

### UserInfo 增加字段
```ts
export interface UserInfo {
  user_id: string;
  username: string;
  email: string | null;
  is_active: boolean;
  // 新增：
  role: string;              // "user" | "admin"
  review_status: string;     // "pending" | "approved" | "rejected" | "disabled"
  last_login_at: string | null;
}
```

### 新增 pending 响应类型
```ts
export interface RegisterPendingResponse {
  user_id: string;
  username: string;
  review_status: "pending";
  message: string;
}
```

### 改造 register() 函数
当前假设 register 总是返回 token。后端现在有两种返回：
- approved: `{access_token, refresh_token, expires_in, user_id, username}`
- pending: `{user_id, username, review_status: "pending", message: "..."}`

改为检测 `review_status === "pending"`：
- pending → 返回 `RegisterPendingResponse`，不存 token
- 有 token → 正常存 token 并返回 UserInfo

```ts
export async function register(
  username: string, password: string, email?: string
): Promise<UserInfo | RegisterPendingResponse> {
  const body: Record<string, string> = { username, password };
  if (email) body.email = email;

  const data = await apiCall<{
    access_token?: string; refresh_token?: string;
    expires_in?: number; username: string; user_id: string;
    review_status?: string; message?: string;
  }>("/api/v1/auth/register", body);

  if (data.review_status === "pending") {
    return { user_id: data.user_id, username: data.username, review_status: "pending", message: data.message! };
  }

  storeAuthTokens(data.access_token!, data.refresh_token!, data.expires_in!);
  const user: UserInfo = {
    user_id: data.user_id, username: data.username,
    email: email || null, is_active: true,
    role: "user", review_status: "approved", last_login_at: null,
  };
  storeUserInfo(user);
  return user;
}
```

## 改动 2: `web/src/contexts/AuthContext.tsx`

### 增加类型和状态
```ts
export type RegisterResult =
  | { type: "pending"; user_id: string; username: string; message: string }
  | { type: "success"; user: UserInfo };
```

- `AuthState` 新增 `reviewStatus: string | null`
- `AuthContextValue` 导出 `reviewStatus`

### 改造 register callback
```ts
const register = useCallback(async (username, password, email) => {
  const result = await apiRegister(username, password, email);
  if ("review_status" in result && result.review_status === "pending") {
    return { type: "pending" as const, ...result };
  }
  const user = result as UserInfo;
  setUser(user);
  return { type: "success" as const, user };
}, []);
```

### init effect
`fetchUserInfo` 返回的 UserInfo 已包含 `role` / `review_status`，直接存。设置 `reviewStatus`。

## 规则
1. 不要改 login 逻辑（login 不会返回 pending，后端直接 403）
2. 保持 AUTH_ENABLED=false 匿名模式不变
3. TypeScript 类型精确，不用 any
4. **只改代码，不要重启 dev server**
