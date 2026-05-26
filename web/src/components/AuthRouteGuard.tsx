"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import LoginCTA from "@/components/LoginCTA";

export default function AuthRouteGuard({
  children,
  requireAuth = true,
}: {
  children: React.ReactNode;
  requireAuth?: boolean;
}) {
  const { user, isLoading, authConfig } = useAuth();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!isLoading && authConfig) {
      if (authConfig.auth_enabled && requireAuth && !user) {
        // Auth enabled, no user — show prompt instead of redirect
        setChecking(false);
      } else {
        setChecking(false);
      }
    }
  }, [user, isLoading, authConfig, requireAuth]);

  if (isLoading || checking) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4" />
          <p className="text-gray-500">加载中...</p>
        </div>
      </div>
    );
  }

  // Auth enabled + require auth + no user → show login prompt
  if (authConfig?.auth_enabled && requireAuth && !user) {
    return <LoginCTA />;
  }

  return <>{children}</>;
}
