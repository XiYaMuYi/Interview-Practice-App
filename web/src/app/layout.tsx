import type { Metadata } from "next";
import localFont from "next/font/local";
import Link from "next/link";
import { AuthProvider } from "@/contexts/AuthContext";
import HeaderNav from "@/components/HeaderNav";
import UserMenu from "@/components/UserMenu";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "AI 面试知识库",
  description: "面向 AI 应用开发工程师的面试题智能知识库与训练系统",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="scroll-smooth">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-screen bg-app-bg text-app-fg`}
      >
        <AuthProvider>
          <div className="app-shell">
            <header className="sticky top-0 z-50 border-b border-white/60 bg-white/75 backdrop-blur-xl shadow-[0_1px_0_rgba(15,23,42,0.04)]">
              <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
                <Link href="/" className="group flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 via-cyan-500 to-teal-500 text-sm font-bold text-white shadow-[0_10px_24px_rgba(14,165,233,0.28)] transition-transform duration-300 group-hover:scale-[1.03]">
                    AI
                  </span>
                  <div className="flex flex-col leading-tight">
                    <span className="text-sm font-semibold tracking-wide text-slate-900 sm:text-base">
                      AI 面试知识库
                    </span>
                    <span className="hidden text-xs text-slate-500 sm:block">
                      让学习、刷题与面试训练形成闭环
                    </span>
                  </div>
                </Link>

                <HeaderNav />

                <UserMenu />
              </div>
            </header>

            <main className="relative mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-10">
              <div className="app-main-frame">{children}</div>
            </main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
