import Link from "next/link";

export default function Home() {
  const features = [
    {
      title: "题目管理",
      description: "浏览、搜索和管理面试题目库",
      href: "/questions",
      icon: "📋",
    },
    {
      title: "批量导入",
      description: "从文本或文件批量导入面试题目",
      href: "/import",
      icon: "📥",
    },
    {
      title: "学习练习",
      description: "AI 辅助的面试模拟练习",
      href: "/study",
      icon: "🎯",
    },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          欢迎使用面试练习平台
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          导入题目、分类管理、AI 模拟面试，帮助你系统地准备技术面试
        </p>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        {features.map((feature) => (
          <Link
            key={feature.href}
            href={feature.href}
            className="bg-white rounded-xl shadow-sm border p-6 hover:shadow-md hover:border-blue-300 transition-all group"
          >
            <div className="text-4xl mb-4">{feature.icon}</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2 group-hover:text-blue-600 transition-colors">
              {feature.title}
            </h3>
            <p className="text-gray-600">{feature.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
