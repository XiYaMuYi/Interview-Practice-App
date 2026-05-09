type SourceType = "resume" | "file" | "text" | "manual" | "ai" | string;

interface SourceBadgeProps {
  source: SourceType;
  size?: "sm" | "md";
}

const config: Record<string, { label: string; cls: string }> = {
  resume: { label: "简历生成", cls: "bg-rose-100 text-rose-700" },
  file:   { label: "文件导入", cls: "bg-blue-100 text-blue-700" },
  text:   { label: "文本导入", cls: "bg-teal-100 text-teal-700" },
  manual: { label: "手动录入", cls: "bg-gray-100 text-gray-700" },
  ai:     { label: "AI 生成",  cls: "bg-violet-100 text-violet-700" },
};

export default function SourceBadge({ source, size = "sm" }: SourceBadgeProps) {
  const { label, cls } = config[source] ?? { label: source, cls: "bg-gray-100 text-gray-600" };
  const sizeCls = size === "sm"
    ? "px-2 py-0.5 text-xs"
    : "px-3 py-1 text-sm";

  return (
    <span className={`inline-block rounded font-medium ${sizeCls} ${cls}`}>
      {label}
    </span>
  );
}
