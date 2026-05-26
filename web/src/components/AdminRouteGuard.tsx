"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";

export default function AdminRouteGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!isLoading) {
      if (!user || user.role !== "admin") {
        router.push("/");
      } else {
        setChecking(false);
      }
    }
  }, [user, isLoading, router]);

  if (isLoading || checking) return <div className="p-8">检查权限...</div>;
  return <>{children}</>;
}
