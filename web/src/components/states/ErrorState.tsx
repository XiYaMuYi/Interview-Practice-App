"use client";

type ErrorCategory = "network" | "backend" | "model" | "parse" | "auth" | "unknown";

interface ErrorStateProps {
  title?: string;
  message?: string;
  category?: ErrorCategory;
  onRetry?: () => void;
  detail?: string;
}

const categoryConfig: Record<ErrorCategory, { title: string; icon: string; color: string }> = {
  network: { title: "网络连接异常", icon: "wifi-off", color: "text-orange-600" },
  backend: { title: "服务端异常", icon: "server", color: "text-red-600" },
  model: { title: "AI 模型异常", icon: "brain", color: "text-purple-600" },
  parse: { title: "解析异常", icon: "file", color: "text-yellow-600" },
  auth: { title: "认证异常", icon: "lock", color: "text-gray-600" },
  unknown: { title: "未知错误", icon: "warning", color: "text-gray-600" },
};

function detectCategory(error: string): ErrorCategory {
  const lower = error.toLowerCase();
  if (lower.includes("network") || lower.includes("连接") || lower.includes("econnrefused")) return "network";
  if (lower.includes("model") || lower.includes("模型") || lower.includes("token") || lower.includes("rate limit")) return "model";
  if (lower.includes("parse") || lower.includes("解析") || lower.includes("format")) return "parse";
  if (lower.includes("auth") || lower.includes("认证") || lower.includes("401") || lower.includes("403")) return "auth";
  if (lower.includes("500") || lower.includes("internal") || lower.includes("服务端")) return "backend";
  return "unknown";
}

export default function ErrorState({
  title,
  message = "获取数据失败",
  category,
  onRetry,
  detail,
}: ErrorStateProps) {
  const cat = category ?? detectCategory(message);
  const config = categoryConfig[cat];
  const displayTitle = title ?? config.title;

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
      <div className={`text-3xl mb-3 ${config.color}`}>
        <svg className="mx-auto h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
        </svg>
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mb-1">{displayTitle}</h3>
      <p className="text-sm text-gray-600 mb-4">{message}</p>
      {detail && (
        <p className="text-xs text-gray-400 mb-4 font-mono bg-red-100/50 rounded px-3 py-2 max-w-md mx-auto">
          {detail}
        </p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-5 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors"
        >
          重试
        </button>
      )}
    </div>
  );
}
