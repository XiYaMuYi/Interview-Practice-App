# Phase 3 Task 3/4: Admin 审核页面

## 目标
创建 `/admin/review` 页面，管理员可以查看 pending 用户列表并通过/拒绝。

## 后端 API（已在 Phase 1 完成）
- `GET /api/v1/auth/admin/users/pending` → 返回 pending 用户列表
- `POST /api/v1/auth/admin/users/{user_id}/review` → body: `{ action: "approved" | "rejected" }`

## 前端 API 调用
### 在 `web/src/lib/auth.ts` 新增两个函数：

```ts
export interface AdminUserListItem {
  user_id: string;
  username: string;
  email: string | null;
  created_at: string;
  role: string;
  review_status: string;
}

export async function listPendingUsers(accessToken?: string): Promise<AdminUserListItem[]> {
  const token = accessToken || getAccessToken();
  if (!token) throw new Error("No access token");
  const res = await fetch("/api/v1/auth/admin/users/pending", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Failed to list pending users: ${res.status}`);
  return res.json();
}

export async function reviewUser(
  userId: string,
  action: "approved" | "rejected",
  accessToken?: string
): Promise<void> {
  const token = accessToken || getAccessToken();
  if (!token) throw new Error("No access token");
  const res = await fetch(`/api/v1/auth/admin/users/${userId}/review`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw new Error(`Failed to review user: ${res.status}`);
}
```

## 创建 `web/src/app/admin/review/page.tsx`

页面功能：
1. 加载时调用 `listPendingUsers()` 获取列表
2. 显示表格：用户名、邮箱、注册时间
3. 每行有"通过"和"拒绝"按钮
4. 操作成功后刷新列表
5. 如果列表为空，显示"暂无待审核用户"

简化实现（MVP）：
```tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { getAccessToken, listPendingUsers, reviewUser, type AdminUserListItem } from "@/lib/auth";
import { useRouter } from "next/navigation";

export default function AdminReviewPage() {
  const { user, reviewStatus } = useAuth();
  const router = useRouter();
  const [pending, setPending] = useState<AdminUserListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 非管理员重定向
  useEffect(() => {
    if (!loading && user?.role !== "admin") {
      router.push("/");
    }
  }, [user, loading, router]);

  const load = useCallback(async () => {
    try {
      const data = await listPendingUsers();
      setPending(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleReview = async (userId: string, action: "approved" | "rejected") => {
    try {
      await reviewUser(userId, action);
      // 从列表移除
      setPending(prev => prev.filter(u => u.user_id !== userId));
    } catch (e: any) {
      alert(e.message);
    }
  };

  if (loading) return <div className="p-8">加载中...</div>;
  if (error) return <div className="p-8 text-red-500">加载失败: {error}</div>;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">用户审核</h1>
      {pending.length === 0 ? (
        <p className="text-gray-500">暂无待审核用户</p>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left">用户名</th>
                <th className="px-4 py-3 text-left">邮箱</th>
                <th className="px-4 py-3 text-left">注册时间</th>
                <th className="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {pending.map(u => (
                <tr key={u.user_id} className="border-t">
                  <td className="px-4 py-3">{u.username}</td>
                  <td className="px-4 py-3">{u.email || "—"}</td>
                  <td className="px-4 py-3">{new Date(u.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-right space-x-2">
                    <button
                      onClick={() => handleReview(u.user_id, "approved")}
                      className="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600"
                    >
                      通过
                    </button>
                    <button
                      onClick={() => handleReview(u.user_id, "rejected")}
                      className="px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600"
                    >
                      拒绝
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

## 规则
1. **只改代码，不要重启 dev server**
2. 在 `auth.ts` 中新增函数，不要改动已有的 login/register/fetchUserInfo 等
3. TypeScript 类型精确，不用 any（catch 块用 `e: any` 可以，其他地方不行）
