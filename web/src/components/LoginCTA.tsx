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
