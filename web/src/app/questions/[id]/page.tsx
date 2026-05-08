"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import axios from "axios";

interface TagInfo {
  tag_name: string | null;
  tag_type: string | null;
  source_type: string | null;
  confidence: number | null;
}

interface KnowledgeNode {
  node_name: string | null;
  node_type: string | null;
  relation_type: string | null;
  confidence: number | null;
}

interface QuestionDetail {
  id: string;
  title: string;
  content: string | null;
  source_type: string | null;
  source_ref: string | null;
  source_excerpt: string | null;
  question_type: string | null;
  domain_type: string | null;
  difficulty_level: number | null;
  difficulty_score: number | null;
  answer_summary: string | null;
  answer_detail: string | null;
  explanation: string | null;
  common_pitfalls: string | null;
  review_status: string | null;
  created_at: string;
  tags: TagInfo[];
  knowledge_nodes: KnowledgeNode[];
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

// Render content with simple markdown-style formatting
function MarkdownContent({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1">
      {lines.map((line, i) => {
        // headings
        if (line.startsWith("### ")) {
          return (
            <h3 key={i} className="text-base font-semibold mt-3 mb-1">
              {line.slice(4)}
            </h3>
          );
        }
        if (line.startsWith("## ")) {
          return (
            <h2 key={i} className="text-lg font-semibold mt-4 mb-1">
              {line.slice(3)}
            </h2>
          );
        }
        if (line.startsWith("# ")) {
          return (
            <h1 key={i} className="text-xl font-bold mt-4 mb-1">
              {line.slice(2)}
            </h1>
          );
        }
        // bold
        if (line.startsWith("**") && line.endsWith("**")) {
          return (
            <p key={i} className="font-semibold mt-2">
              {line.slice(2, -2)}
            </p>
          );
        }
        // bullet
        if (line.startsWith("- ") || line.startsWith("* ")) {
          return (
            <li key={i} className="ml-4 list-disc text-gray-700">
              {line.slice(2)}
            </li>
          );
        }
        // numbered
        const numMatch = line.match(/^(\d+)\.\s/);
        if (numMatch) {
          return (
            <li key={i} className="ml-4 list-decimal text-gray-700">
              {line.slice(numMatch[0].length)}
            </li>
          );
        }
        // code block markers (skip them, render content in monospace)
        if (line.trim() === "```") return null;
        // empty line
        if (line.trim() === "") return <br key={i} />;
        // default paragraph
        return (
          <p key={i} className="text-gray-700 leading-relaxed">
            {line}
          </p>
        );
      })}
    </div>
  );
}

export default function QuestionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [detail, setDetail] = useState<QuestionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 生成讲解
  const [generating, setGenerating] = useState(false);
  const [generatedExplanation, setGeneratedExplanation] = useState<string | null>(null);

  useEffect(() => {
    async function fetch() {
      try {
        const res = await axios.get(`/api/v1/questions/${id}/detail`);
        setDetail(res.data);
      } catch {
        setError("获取题目详情失败");
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, [id]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await axios.post(`/api/v1/questions/${id}/explain`);
      setGeneratedExplanation(res.data.explanation || res.data.content || JSON.stringify(res.data));
    } catch {
      // 接口可能尚未实现
      setGeneratedExplanation("生成讲解接口尚未实现，后端待开发。");
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center text-gray-500">
        加载中...
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center text-red-500">
        {error || "题目不存在"}
        <div className="mt-4">
          <Link
            href="/questions"
            className="text-blue-600 hover:underline"
          >
            返回列表
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Back button */}
      <button
        onClick={() => router.back()}
        className="mb-6 text-sm text-gray-600 hover:text-gray-900 transition-colors flex items-center gap-1"
      >
        &larr; 返回列表
      </button>

      {/* Header */}
      <h1 className="text-2xl font-bold text-gray-900 mb-4">
        {detail.title || "无标题"}
      </h1>

      {/* Meta badges */}
      <div className="flex flex-wrap gap-2 mb-6">
        <span className="px-2 py-1 rounded text-xs font-medium bg-purple-100 text-purple-700">
          {typeLabel(detail.question_type)}
        </span>
        <span className="px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700">
          {domainLabel(detail.domain_type)}
        </span>
        <span
          className={`px-2 py-1 rounded text-xs font-medium ${difficultyColor(detail.difficulty_level)}`}
        >
          {difficultyText(detail.difficulty_level)}
        </span>
        {detail.difficulty_score != null && (
          <span className="px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-600">
            评分 {detail.difficulty_score.toFixed(1)}
          </span>
        )}
        {detail.review_status && (
          <span className="px-2 py-1 rounded text-xs font-medium bg-indigo-100 text-indigo-700">
            {detail.review_status}
          </span>
        )}
      </div>

      {/* Content */}
      {detail.content && (
        <section className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">题目内容</h2>
          <MarkdownContent text={detail.content} />
        </section>
      )}

      {/* Source info */}
      {(detail.source_type || detail.source_ref || detail.source_excerpt) && (
        <section className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">来源信息</h2>
          <dl className="space-y-2 text-sm">
            {detail.source_type && (
              <div className="flex gap-2">
                <dt className="text-gray-500 w-24 shrink-0">来源类型</dt>
                <dd className="text-gray-800">{detail.source_type}</dd>
              </div>
            )}
            {detail.source_ref && (
              <div className="flex gap-2">
                <dt className="text-gray-500 w-24 shrink-0">来源引用</dt>
                <dd className="text-gray-800">{detail.source_ref}</dd>
              </div>
            )}
            {detail.source_excerpt && (
              <div className="flex gap-2">
                <dt className="text-gray-500 w-24 shrink-0">原文摘录</dt>
                <dd className="text-gray-800 italic">{detail.source_excerpt}</dd>
              </div>
            )}
          </dl>
        </section>
      )}

      {/* Tags */}
      {detail.tags.length > 0 && (
        <section className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">标签</h2>
          <div className="flex flex-wrap gap-2">
            {detail.tags.map((t, i) => (
              <span
                key={i}
                className="px-3 py-1 bg-gray-100 text-gray-700 rounded text-sm"
              >
                {t.tag_name}
                {t.tag_type && <span className="text-gray-400 ml-1">({t.tag_type})</span>}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Knowledge nodes */}
      {detail.knowledge_nodes.length > 0 && (
        <section className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">知识节点</h2>
          <div className="flex flex-wrap gap-2">
            {detail.knowledge_nodes.map((n, i) => (
              <span
                key={i}
                className="px-3 py-1 bg-teal-50 text-teal-700 rounded text-sm"
              >
                {n.node_name}
                {n.relation_type && (
                  <span className="text-teal-400 ml-1">[{n.relation_type}]</span>
                )}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Answer summary */}
      {detail.answer_summary && (
        <section className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">答案摘要</h2>
          <MarkdownContent text={detail.answer_summary} />
        </section>
      )}

      {/* Answer detail */}
      {detail.answer_detail && (
        <section className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">详细答案</h2>
          <MarkdownContent text={detail.answer_detail} />
        </section>
      )}

      {/* Explanation */}
      {detail.explanation && (
        <section className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">讲解</h2>
          <MarkdownContent text={detail.explanation} />
        </section>
      )}

      {/* Common pitfalls */}
      {detail.common_pitfalls && (
        <section className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">常见误区</h2>
          <MarkdownContent text={detail.common_pitfalls} />
        </section>
      )}

      {/* Generate explanation button */}
      <div className="mt-8 flex gap-4">
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {generating ? "生成中..." : "生成讲解"}
        </button>
      </div>

      {generatedExplanation && (
        <section className="bg-amber-50 border border-amber-200 rounded-lg p-6 mt-6">
          <h2 className="text-lg font-semibold text-amber-900 mb-3">AI 生成的讲解</h2>
          <MarkdownContent text={generatedExplanation} />
        </section>
      )}
    </div>
  );
}
