import Link from "next/link";
import SourceBadge from "./SourceBadge";

interface Question {
  id: string;
  title: string;
  question_type: string | null;
  domain_type: string | null;
  difficulty_level: number | null;
  source_type?: string;
}

interface QuestionCardProps {
  question: Question;
}

const typeLabel = (t: string | null) => {
  if (!t) return "未分类";
  const map: Record<string, string> = {
    concept: "概念",
    code: "代码",
    scenario: "场景",
    system_design: "系统设计",
    behavioral: "行为",
  };
  return map[t] || t;
};

const domainLabel = (d: string | null) => {
  if (!d) return "未分类";
  const map: Record<string, string> = {
    RAG: "RAG",
    Backend: "后端",
    Frontend: "前端",
    Database: "数据库",
    DevOps: "DevOps",
    Algorithm: "算法",
    ML: "机器学习",
  };
  return map[d] || d;
};

const difficultyText = (level: number | null) => {
  if (level == null) return "未定级";
  const map: Record<number, string> = {
    1: "入门",
    2: "简单",
    3: "中等",
    4: "困难",
    5: "专家",
  };
  return map[level] || `${level}`;
};

const difficultyColor = (level: number | null) => {
  if (level == null) return "bg-gray-100 text-gray-600";
  const map: Record<number, string> = {
    1: "bg-green-100 text-green-700",
    2: "bg-lime-100 text-lime-700",
    3: "bg-yellow-100 text-yellow-700",
    4: "bg-orange-100 text-orange-700",
    5: "bg-red-100 text-red-700",
  };
  return map[level] || "bg-gray-100 text-gray-600";
};

export default function QuestionCard({ question }: QuestionCardProps) {
  return (
    <Link
      href={`/questions/${question.id}`}
      className="block bg-white rounded-lg shadow-sm border p-5 hover:shadow-md hover:border-blue-300 transition-all"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-semibold text-gray-900 truncate">
            {question.title || "无标题"}
          </h2>
        </div>
        <div className="flex gap-2 shrink-0 flex-wrap justify-end items-center">
          {question.source_type && (
            <SourceBadge source={question.source_type} />
          )}
          <span className="px-2 py-1 rounded text-xs font-medium bg-purple-100 text-purple-700">
            {typeLabel(question.question_type)}
          </span>
          <span className="px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700">
            {domainLabel(question.domain_type)}
          </span>
          <span
            className={`px-2 py-1 rounded text-xs font-medium ${difficultyColor(question.difficulty_level)}`}
          >
            {difficultyText(question.difficulty_level)}
          </span>
        </div>
      </div>
    </Link>
  );
}
