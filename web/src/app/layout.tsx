import type { Metadata } from "next";
import localFont from "next/font/local";
import Link from "next/link";
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
  title: "面试练习",
  description: "面试练习平台 - 导入、练习和掌握面试题目",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-screen bg-gray-50`}
      >
        <nav className="bg-white shadow-sm border-b">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16 items-center">
              <Link href="/" className="text-xl font-bold text-gray-900">
                面试练习
              </Link>
              <div className="flex gap-6">
                <Link
                  href="/"
                  className="text-gray-600 hover:text-gray-900 transition-colors"
                >
                  首页
                </Link>
                <Link
                  href="/questions"
                  className="text-gray-600 hover:text-gray-900 transition-colors"
                >
                  题目
                </Link>
                <Link
                  href="/import"
                  className="text-gray-600 hover:text-gray-900 transition-colors"
                >
                  导入
                </Link>
                <Link
                  href="/study"
                  className="text-gray-600 hover:text-gray-900 transition-colors"
                >
                  学习
                </Link>
                <Link
                  href="/interview"
                  className="text-gray-600 hover:text-gray-900 transition-colors"
                >
                  面试
                </Link>
                <Link
                  href="/stats"
                  className="text-gray-600 hover:text-gray-900 transition-colors"
                >
                  统计
                </Link>
              </div>
            </div>
          </div>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
