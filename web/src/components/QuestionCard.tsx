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

const difficultyDiffClass = (level: number | null) => {
  if (level == null || level < 1 || level > 5) return "secondary-chip";
  return `diff-${level}`;
};

export default function QuestionCard({ question }: QuestionCardProps) {
  return (
    <Link
      href={`/questions/${question.id}`}
      className="block soft-card soft-card-hover p-5"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-semibold text-slate-900 truncate">
            {question.title || "无标题"}
          </h2>
        </div>
        <div className="flex gap-2 shrink-0 flex-wrap justify-end items-center">
          {question.source_type && (
            <SourceBadge source={question.source_type} />
          )}
          <span className="secondary-chip">
            {typeLabel(question.question_type)}
          </span>
          <span className="primary-chip">
            {domainLabel(question.domain_type)}
          </span>
          <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${difficultyDiffClass(question.difficulty_level)}`}>
            {difficultyText(question.difficulty_level)}
          </span>
        </div>
      </div>
    </Link>
  );
}
