# Phase 4 Task 4/4: 统一登录引导组件 + 拦截体验优化

## 目标
创建可复用的 `LoginCTA` 组件，替换各页面中散落的登录提示，优化未登录拦截体验。

## 改动 1: 创建 `web/src/components/LoginCTA.tsx`

```tsx
"use client";

import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export default function LoginCTA({
  title = "需要登录",
  message = "请先登录以访问此功能。",
  variant = "centered",
}: {
  title?: string;
  message?: string;
  variant?: "centered" | "inline";
}) {
  const { authConfig } = useAuth();
  const isAuthEnabled = authConfig?.auth_enabled ?? true;

  if (!isAuthEnabled) return null;

  if (variant === "inline") {
    return (
      <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-sky-800">{title}</p>
          <p className="text-sm text-sky-600">{message}</p>
        </div>
        <Link
          href="/login"
          className="ml-4 flex-shrink-0 text-sm font-medium text-sky-600 hover:text-sky-800"
        >
          去登录 →
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-center p-8">
        <h2 className="text-2xl font-bold mb-4">{title}</h2>
        <p className="text-gray-600 mb-6">{message}</p>
        <Link
          href="/login"
          className="px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          去登录
        </Link>
      </div>
    </div>
  );
}
```

## 改动 2: 在 AuthRouteGuard 中使用 LoginCTA

修改 `web/src/components/AuthRouteGuard.tsx`，将硬编码的登录提示替换为 `<LoginCTA />` 组件。

## 改动 3: 在 questions 页面使用 LoginCTA inline 变体

修改 `web/src/app/questions/page.tsx`，使用 `<LoginCTA variant="inline" message="登录后可保存学习记录、收藏题目、使用 AI 讲解" />` 替换 Task 3 中添加的硬编码横幅。

## 规则
1. **只改代码，不要重启 dev server**
2. LoginCTA 组件保持简洁，不做复杂逻辑
3. TypeScript 类型精确
