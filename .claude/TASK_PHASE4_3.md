# Phase 4 Task 3/4: 公共题库匿名浏览 + 登录引导 CTA

## 目标
`/questions` 页面允许匿名用户浏览题目，但显示登录引导 CTA（鼓励注册/登录）。

## 改动: `web/src/app/questions/page.tsx`

在页面顶部（搜索栏下方、列表上方）添加匿名登录引导横幅：

```tsx
// 在组件内
const { user, authConfig } = useAuth();
const isAuthEnabled = authConfig?.auth_enabled ?? true;
const isAnonymous = isAuthEnabled && !user;

// 在 return 中，搜索栏之后：
{isAnonymous && (
  <div className="mb-6 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 flex items-center justify-between">
    <p className="text-sm text-sky-700">
      💡 登录后可保存学习记录、收藏题目、使用 AI 讲解
    </p>
    <Link
      href="/login"
      className="ml-4 flex-shrink-0 text-sm font-medium text-sky-600 hover:text-sky-800"
    >
      去登录 →
    </Link>
  </div>
)}
```

保持题目列表的加载、搜索、分页逻辑不变。

## 规则
1. **只改代码，不要重启 dev server**
2. 不改变题目列表的任何现有逻辑
3. 只在 auth 开启且未登录时显示横幅
