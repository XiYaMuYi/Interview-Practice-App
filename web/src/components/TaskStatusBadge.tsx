type TaskStatus = "uploading" | "parsing" | "structured" | "done" | "failed" | string;

interface TaskStatusBadgeProps {
  status: TaskStatus;
}

const config: Record<string, { label: string; cls: string; icon?: string }> = {
  uploading:    { label: "上传中",   cls: "bg-blue-100 text-blue-700",     icon: "upload" },
  parsing:      { label: "解析中",   cls: "bg-yellow-100 text-yellow-700", icon: "spinner" },
  structured:   { label: "结构化完成", cls: "bg-indigo-100 text-indigo-700" },
  done:         { label: "已完成",   cls: "bg-green-100 text-green-700",   icon: "check" },
  failed:       { label: "已失败",   cls: "bg-red-100 text-red-700",       icon: "error" },
};

export default function TaskStatusBadge({ status }: TaskStatusBadgeProps) {
  const { label, cls } = config[status] ?? { label: status, cls: "bg-gray-100 text-gray-600" };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}
