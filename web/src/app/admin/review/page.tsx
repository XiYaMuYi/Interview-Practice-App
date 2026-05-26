"use client";

import { useState, useEffect, useCallback } from "react";
import { listPendingUsers, reviewUser, type AdminUserListItem } from "@/lib/auth";
import AdminRouteGuard from "@/components/AdminRouteGuard";

export default function AdminReviewPage() {
  return (
    <AdminRouteGuard>
      <AdminReviewContent />
    </AdminRouteGuard>
  );
}

function AdminReviewContent() {
  const [pending, setPending] = useState<AdminUserListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
