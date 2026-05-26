/**
 * Login page — handles both login and registration with a toggle.
 * When auth is disabled on the backend, shows a notice and allows anonymous access.
 */
"use client";

import { useState, useEffect, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const { login, register, isLoading, authConfig, isAuthenticated } =
    useAuth();

  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Redirect if already logged in or auth is disabled
  useEffect(() => {
    if (!isLoading) {
      if (isAuthenticated || authConfig?.auth_enabled === false) {
        router.push("/");
      }
    }
  }, [isLoading, isAuthenticated, authConfig, router]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!username.trim() || !password.trim()) {
      setError("请填写用户名和密码");
      return;
    }

    setIsSubmitting(true);
    try {
      if (mode === "login") {
        await login(username.trim(), password);
        router.push("/");
      } else {
        const result = await register(
          username.trim(),
          password,
          email.trim() || undefined
        );
        if (result.type === "pending") {
          router.push("/pending");
        } else {
          router.push("/");
        }
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "操作失败，请重试";
      // Provide more user-friendly messages for common errors
      if (message.includes("401") || message.toLowerCase().includes("password")) {
        setError(mode === "login" ? "用户名或密码错误" : "注册失败，请检查输入");
      } else if (message.includes("审核中") || message.includes("pending")) {
        setError("账号正在审核中，请耐心等待管理员审核");
      } else if (message.includes("拒绝") || message.includes("rejected")) {
        setError("账号已被拒绝，无法登录");
      } else if (message.includes("403")) {
        setError("账号尚未通过审核或已被禁用，请联系管理员");
      } else if (message.includes("409") || message.includes("exists")) {
        setError("该用户名已被注册");
      } else {
        setError(message);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-slate-500">加载中...</div>
      </div>
    );
  }

  // Auth disabled — show notice and redirect
  if (authConfig?.auth_enabled === false) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="soft-card p-8 text-center max-w-md">
          <div className="text-4xl mb-4">🔓</div>
          <h2 className="text-xl font-semibold mb-2">无需登录</h2>
          <p className="text-slate-600 mb-4">
            当前系统处于公开模式，所有功能均可匿名使用。
          </p>
          <button
            onClick={() => router.push("/")}
            className="btn-primary"
          >
            返回首页
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center px-4">
      <div className="soft-card w-full max-w-md p-8">
        {/* Header */}
        <div className="text-center mb-6">
          <div className="text-4xl mb-2">🔐</div>
          <h1 className="text-2xl font-bold text-slate-900">
            {mode === "login" ? "登录" : "注册"}
          </h1>
          <p className="text-slate-500 mt-1">
            {mode === "login"
              ? "登录以使用完整功能"
              : "创建账号以开始使用"}
          </p>
        </div>

        {/* Mode toggle */}
        <div className="flex rounded-lg bg-slate-100 p-1 mb-6">
          <button
            type="button"
            onClick={() => {
              setMode("login");
              setError(null);
            }}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
              mode === "login"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            登录
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("register");
              setError(null);
            }}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
              mode === "register"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            注册
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Username */}
          <div>
            <label
              htmlFor="username"
              className="block text-sm font-medium text-slate-700 mb-1"
            >
              用户名
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
              autoComplete="username"
              className="form-input w-full"
              disabled={isSubmitting}
            />
          </div>

          {/* Password */}
          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-slate-700 mb-1"
            >
              密码
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              className="form-input w-full"
              disabled={isSubmitting}
            />
          </div>

          {/* Email (register only) */}
          {mode === "register" && (
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-slate-700 mb-1"
              >
                邮箱
                <span className="text-slate-400 font-normal ml-1">（可选）</span>
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="请输入邮箱（可选）"
                autoComplete="email"
                className="form-input w-full"
                disabled={isSubmitting}
              />
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={isSubmitting}
            className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting
              ? mode === "login"
                ? "登录中..."
                : "注册中..."
              : mode === "login"
              ? "登录"
              : "注册"}
          </button>
        </form>

        {/* Footer link */}
        <p className="text-center text-sm text-slate-500 mt-6">
          {mode === "login" ? (
            <>
              还没有账号？{" "}
              <button
                type="button"
                onClick={() => {
                  setMode("register");
                  setError(null);
                }}
                className="text-sky-600 hover:text-sky-700 font-medium"
              >
                立即注册
              </button>
            </>
          ) : (
            <>
              已有账号？{" "}
              <button
                type="button"
                onClick={() => {
                  setMode("login");
                  setError(null);
                }}
                className="text-sky-600 hover:text-sky-700 font-medium"
              >
                返回登录
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
