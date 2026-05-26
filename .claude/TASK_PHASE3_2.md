# Phase 3 Task 2/4: Pending 页面 + 登录错误处理

## 目标
1. 创建 `/pending` 审核等待页面
2. 改造登录页适配 pending 流程和登录错误处理

## 改动 1: 创建 `web/src/app/pending/page.tsx`

页面逻辑：
- 显示"账号正在审核中，请耐心等待"
- 轮询 `/api/v1/auth/me`（使用 localStorage 中的 token 检测，但 pending 用户没有 token）
- 实际上 pending 用户没有 token，所以轮询应该用 user_id 去查状态
- 更好的方案：显示"等待管理员审核"的提示 + 退出按钮（清缓存回到登录页）

简化版（MVP）：
```tsx
"use client";
import { useRouter } from "next/navigation";
import { clearAuth } from "@/lib/auth";

export default function PendingPage() {
  const router = useRouter();

  const handleBack = () => {
    clearAuth();
    router.push("/login");
  };

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-2xl font-bold mb-4">账号审核中</h1>
        <p className="text-gray-600 mb-8">
          您的账号已创建，正在等待管理员审核。审核通过后即可登录使用。
        </p>
        <button onClick={handleBack} className="px-4 py-2 bg-blue-500 text-white rounded">
          返回登录
        </button>
      </div>
    </div>
  );
}
```

## 改动 2: 改造 `web/src/app/login/page.tsx`

### register 分支
当前逻辑：注册成功 → `router.push("/")`
改为：
```ts
const result = await register(username, password, email);
if (result.type === "pending") {
  router.push("/pending");
} else {
  router.push("/");
}
```

### login 错误处理
当前逻辑：`catch (e)` 显示通用错误
改为识别错误类型：
- 403 → 可能是 pending/rejected/disabled → 显示"账号尚未通过审核"或"账号已被拒绝"
- 其他 → 显示原错误信息

注意：login 调用 `apiLogin` 抛出 Error 对象，Error.message 包含后端 detail。根据后端实现：
- pending 用户登录 → 403 `{"detail": "账号正在审核中，请联系管理员"}`
- rejected 用户登录 → 403 `{"detail": "账号已被拒绝，无法登录"}`
- disabled 用户登录 → 401/403

## 规则
1. 不要改 login 的 API 调用逻辑（auth.ts 中的 login 函数不用动）
2. 保持 AUTH_ENABLED=false 匿名模式不变
3. **只改代码，不要重启 dev server**
