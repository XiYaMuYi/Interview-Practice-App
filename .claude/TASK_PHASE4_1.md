# Phase 4 Task 1/4: 创建 AuthRouteGuard 并应用到用户页面

## 目标
创建通用 `AuthRouteGuard` 组件，区分三种情况：
1. **AUTH_ENABLED=false（匿名模式）**：不拦截，直接渲染
2. **AUTH_ENABLED=true 但未登录**：显示"需要登录"提示 + 跳转到登录页的按钮
3. **AUTH_ENABLED=true 且已登录**：直接渲染

## 改动 1: 创建 `web/src/components/AuthRouteGuard.tsx`

```tsx
"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function AuthRouteGuard({
  children,
  requireAuth = true,
}: {
  children: React.ReactNode;
  requireAuth?: boolean;
}) {
  const { user, isLoading, authConfig } = useAuth();
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!isLoading && authConfig) {
      if (authConfig.auth_enabled && requireAuth && !user) {
        // Auth enabled, no user → show prompt instead of redirect
        // Let user choose to login or go back
        setChecking(false);
      } else {
        setChecking(false);
      }
    }
  }, [user, isLoading, authConfig, requireAuth]);

  if (isLoading || checking) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4" />
          <p className="text-gray-500">加载中...</p>
        </div>
      </div>
    );
  }

  // Auth enabled + require auth + no user → show login prompt
  if (authConfig?.auth_enabled && requireAuth && !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center p-8">
          <h2 className="text-2xl font-bold mb-4">需要登录</h2>
          <p className="text-gray-600 mb-6">
            请先登录以访问此功能。
          </p>
          <div className="space-x-4">
            <Link
              href="/login"
              className="px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              去登录
            </Link>
            <button
              onClick={() => router.back()}
              className="px-6 py-2 border border-gray-300 rounded hover:bg-gray-50"
            >
              返回
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
```

## 改动 2: 应用到以下页面

对每个页面，用 `AuthRouteGuard` 包裹页面内容。模式统一：

```tsx
import AuthRouteGuard from "@/components/AuthRouteGuard";

export default function StudyPage() {
  return (
    <AuthRouteGuard>
      {/* 原有全部内容 */}
    </AuthRouteGuard>
  );
}
```

### 需要修改的页面：
1. `web/src/app/study/page.tsx`
2. `web/src/app/exam/page.tsx`
3. `web/src/app/interview/page.tsx`
4. `web/src/app/import/page.tsx`
5. `web/src/app/stats/page.tsx`

### 不需要修改的页面：
- `/` (首页) — 公开
- `/questions` — 公共题库，匿名可浏览（Task 3 处理）
- `/login` — 公开
- `/pending` — 公开
- `/admin/review` — 已有 AdminRouteGuard

## 改动方式
对每个页面，只需在最外层 return 加一层 `<AuthRouteGuard>...</AuthRouteGuard>`，不要改页面内部逻辑。

## 规则
1. **只改代码，不要重启 dev server**
2. 每个页面改动要小，不要重构
3. TypeScript 类型精确
