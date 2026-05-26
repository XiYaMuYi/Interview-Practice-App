# Phase 4: 全站登录保护 + 用户体验闭环

## 背景
Phase 1-3 完成后，后端鉴权和数据隔离已到位，但前端页面（study/exam/interview/import/stats）没有登录保护。匿名用户仍可访问所有页面，登录后也无法获得个性化体验。

## 目标
1. 创建通用 `AuthRouteGuard` 组件，保护需要登录的页面
2. 改造 layout 导航栏，区分匿名/登录/管理员状态
3. 公共题库页面允许匿名浏览但提示登录
4. 创建登录引导组件（CTA）

## 拆分
- **Task 1**: 创建 `AuthRouteGuard.tsx` + 应用到 study/exam/interview/import/stats
- **Task 2**: 改造 `layout.tsx` 导航栏登录态 + UserMenu 匿名模式
- **Task 3**: 公共题库页面 `/questions` 匿名浏览 + 登录引导 CTA
- **Task 4**: 登录引导组件 `LoginCTA` + 未登录拦截优化
