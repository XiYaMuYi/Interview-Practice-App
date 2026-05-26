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
        <button
          onClick={handleBack}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
        >
          返回登录
        </button>
      </div>
    </div>
  );
}
