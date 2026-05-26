"use client";

import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

const publicNavItems = [
  { href: "/", label: "首页" },
  { href: "/questions", label: "题目" },
];

const privateNavItems = [
  { href: "/import", label: "导入" },
  { href: "/study", label: "学习" },
  { href: "/interview", label: "面试" },
  { href: "/exam", label: "考试" },
  { href: "/stats", label: "统计" },
];

export default function HeaderNav() {
  const { user } = useAuth();
  const navItems = [
    ...publicNavItems,
    ...(user ? privateNavItems : []),
    ...(user?.role === "admin" ? [{ href: "/admin/review", label: "审核" }] : []),
  ];

  return (
    <>
      <nav className="hidden items-center gap-1 md:flex">
        {navItems.map((item) => (
          <Link key={item.href} href={item.href} className="nav-link">
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="flex items-center gap-2 md:hidden">
        <Link href="/questions" className="mobile-nav-chip">
          题库
        </Link>
        {user && (
          <Link href="/study" className="mobile-nav-chip">
            学习
          </Link>
        )}
      </div>
    </>
  );
}
