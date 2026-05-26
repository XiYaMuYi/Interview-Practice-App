/**
 * User dropdown — shows login state, username, and logout button in the header.
 */
"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

export default function UserMenu() {
  const { user, isAuthenticated, isLoading, authConfig, logout } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const handleLogout = () => {
    logout();
    setOpen(false);
    router.push("/");
  };

  // Loading state
  if (isLoading) {
    return <div className="h-8 w-8 rounded-full bg-slate-200 animate-pulse" />;
  }

  // Auth disabled — show anonymous indicator
  if (authConfig?.auth_enabled === false) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <span className="hidden sm:inline">公开模式</span>
        <span className="h-8 w-8 rounded-full bg-slate-200 flex items-center justify-center text-sm">
          👤
        </span>
      </div>
    );
  }

  // Not logged in
  if (!isAuthenticated || !user) {
    return (
      <Link
        href="/login"
        className="flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-sky-600 transition-colors px-3 py-1.5 rounded-lg hover:bg-sky-50"
      >
        <span className="hidden sm:inline">登录</span>
        <span className="h-8 w-8 rounded-full bg-slate-200 flex items-center justify-center text-sm">
          👤
        </span>
      </Link>
    );
  }

  // Logged in
  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-sky-600 transition-colors px-3 py-1.5 rounded-lg hover:bg-sky-50"
      >
        <span className="hidden sm:inline">{user.username}</span>
        {user.role === "admin" && (
          <span className="hidden sm:inline px-1.5 py-0.5 text-xs bg-purple-100 text-purple-700 rounded">
            管理员
          </span>
        )}
        {user.review_status === "pending" && (
          <span className="hidden sm:inline px-1.5 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded">
            审核中
          </span>
        )}
        <span className="h-8 w-8 rounded-full bg-gradient-to-br from-sky-500 to-teal-500 flex items-center justify-center text-white text-xs font-bold">
          {user.username.charAt(0).toUpperCase()}
        </span>
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-48 rounded-xl bg-white shadow-lg border border-slate-200 py-2 z-50">
          {/* User info */}
          <div className="px-4 py-2 border-b border-slate-100">
            <div className="text-sm font-medium text-slate-900">
              {user.username}
              {user.role === "admin" && (
                <span className="ml-2 px-1.5 py-0.5 text-xs bg-purple-100 text-purple-700 rounded">
                  管理员
                </span>
              )}
            </div>
            {user.email && (
              <div className="text-xs text-slate-500 truncate">{user.email}</div>
            )}
            {user.review_status === "pending" && (
              <div className="text-xs text-yellow-600 mt-1">审核中</div>
            )}
          </div>

          {/* Admin link */}
          {user.role === "admin" && (
            <Link
              href="/admin/review"
              className="block w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
            >
              审核
            </Link>
          )}

          {/* Actions */}
          <button
            onClick={handleLogout}
            className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
          >
            退出登录
          </button>
        </div>
      )}
    </div>
  );
}
