# Phase 4 Task 2/4: 导航栏登录态 + UserMenu 匿名态

## 目标
改造 `web/src/app/layout.tsx` 的 `HeaderNav`，区分匿名态/登录态的导航项，并在匿名时显示"登录"按钮。

## 改动

### 1. HeaderNav 区分导航项

当前 HeaderNav 显示 `baseNavItems` 给所有人。改为：

```tsx
function HeaderNav() {
  const { user } = useAuth();
  
  const publicItems = [
    { href: "/", label: "首页" },
    { href: "/questions", label: "题目" },
  ];
  
  const privateItems = [
    { href: "/import", label: "导入" },
    { href: "/study", label: "学习" },
    { href: "/interview", label: "面试" },
    { href: "/exam", label: "考试" },
    { href: "/stats", label: "统计" },
  ];
  
  const adminItems = user?.role === "admin"
    ? [{ href: "/admin/review", label: "审核" }]
    : [];
  
  const navItems = [
    ...publicItems,
    ...(user ? privateItems : []),
    ...adminItems,
  ];
  // ... 渲染逻辑不变
}
```

**匿名用户只能看到：首页 + 题目**
**登录用户看到：全部导航项**

### 2. UserMenu 匿名态显示"登录"按钮

在 `web/src/components/UserMenu.tsx` 开头，如果未登录则显示"登录"按钮而非用户头像：

```tsx
// 在组件函数体开头
if (!user) {
  return (
    <Link
      href="/login"
      className="px-4 py-2 text-sm rounded-md bg-sky-500 text-white hover:bg-sky-600 transition"
    >
      登录
    </Link>
  );
}
```

保持原有的 dropdown 逻辑不变，只是加一个 early return。

### 3. 移动端导航也做同样区分

layout.tsx 中的移动端导航（md:hidden 部分）同样改为只显示公开项：

```tsx
<div className="flex items-center gap-2 md:hidden">
  <Link href="/questions" className="mobile-nav-chip">
    题库
  </Link>
</div>
```

## 规则
1. **只改代码，不要重启 dev server**
2. 改动尽量小，保持现有样式不变
3. TypeScript 类型精确
