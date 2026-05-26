# Phase 3 Task 4/4: 路由守卫 + 导航栏管理员入口

## 目标
1. 在导航栏添加"审核"入口（仅管理员可见）
2. 改造 UserMenu 显示审核状态
3. 添加路由守卫中间件，保护 `/admin/*` 路由

## 改动 1: 改造 `web/src/app/layout.tsx`

在 navItems 数组中添加管理员入口（条件渲染）：

当前 navItems 是静态数组。需要改为条件添加：
```tsx
// 在 layout 组件内，拿到 auth 后：
const adminNavItem = user?.role === "admin"
  ? { href: "/admin/review", label: "审核" }
  : null;

const navItems = [
  { href: "/", label: "首页" },
  { href: "/exam", label: "刷题" },
  { href: "/interview", label: "模拟面试" },
  { href: "/import", label: "导入" },
  ...(adminNavItem ? [adminNavItem] : []),
];
```

注意：layout.tsx 中 AuthProvider 包裹了整个 children，navItems 构建在 AuthProvider 内部还是外部？
- 如果 navItems 在 AuthProvider 外部（根组件层级），需要通过一个子组件来消费 auth context
- 创建一个 HeaderNav 组件在 AuthProvider 内部渲染

## 改动 2: 改造 `web/src/components/UserMenu.tsx`

在用户下拉菜单中：
1. 显示用户名旁边加上角色标签（管理员显示 badge）
2. 如果有审核状态且不是 approved，显示状态提示
3. 添加"审核"菜单项（仅管理员可见）

具体改动：
```tsx
// 角色 badge
{user.role === "admin" && (
  <span className="ml-2 px-1.5 py-0.5 text-xs bg-purple-100 text-purple-700 rounded">
    管理员
  </span>
)}

// 审核中提示
{user.review_status === "pending" && (
  <span className="ml-2 px-1.5 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded">
    审核中
  </span>
)}
```

## 改动 3: 创建 `web/src/components/AdminRouteGuard.tsx`

简单的前端路由守卫组件：
```tsx
"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";

export default function AdminRouteGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!isLoading) {
      if (!user || user.role !== "admin") {
        router.push("/");
      } else {
        setChecking(false);
      }
    }
  }, [user, isLoading, router]);

  if (isLoading || checking) return <div className="p-8">检查权限...</div>;
  return <>{children}</>;
}
```

在 `web/src/app/admin/review/page.tsx` 中使用：
```tsx
import AdminRouteGuard from "@/components/AdminRouteGuard";

export default function AdminReviewPage() {
  return (
    <AdminRouteGuard>
      {/* existing page content */}
    </AdminRouteGuard>
  );
}
```

## 规则
1. **只改代码，不要重启 dev server**
2. layout.tsx 改动要小，不要重构整个布局
3. UserMenu.tsx 保持现有功能不变
