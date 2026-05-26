"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import { useTaskEvents } from "@/hooks/useTaskEvents";

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
    1: "diff-1",
    2: "diff-2",
    3: "diff-3",
    4: "diff-4",
    5: "diff-5",
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
  const [generateDepth, setGenerateDepth] = useState<string | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);

  // 流式生成状态
  const [streamingTaskId, setStreamingTaskId] = useState<string | null>(null);
  const [streamingDepth, setStreamingDepth] = useState<string | null>(null);
  const [streamingComplete, setStreamingComplete] = useState(false);

  useEffect(() => {
    async function fetch() {
      try {
        const res = await api.get(`/api/v1/questions/${id}/detail`);
        setDetail(res.data);
      } catch {
        setError("获取题目详情失败");
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, [id]);

  // useTaskEvents hook for streaming — auto-connects when streamingTaskId is set
  const {
    accumulatedContent,
    currentPhase: streamPhase,
    progress: streamProgress,
    isConnected: streamConnected,
    reset: resetStream,
  } = useTaskEvents(streamingTaskId, {
    onDone: (finalState) => {
      setStreamingComplete(true);
      const finalContent = finalState.content || accumulatedContent;
      if (finalContent) {
        setGeneratedExplanation(finalContent);
      }
    },
  });

  const handleGenerate = async (depth: "brief" | "standard" | "deep") => {
    // Use streaming endpoint — the page already supports streaming via useTaskEvents
    resetStream();
    setStreamingTaskId(null);
    setGenerateError(null);
    setStreamingComplete(false);
    setStreamingDepth(depth);
    setGenerateDepth(depth);
    setGeneratedExplanation(null);
    setGenerating(true);
    try {
      const res = await api.post(`/api/v1/ai/explain-stream`, {
        question_id: id,
        depth,
      });
      const taskId = res.data.task_id;
      if (!taskId) {
        setGenerateError("未获取到任务ID，流式生成启动失败");
        return;
      }
      setStreamingTaskId(taskId);
    } catch {
      setGenerateError("启动流式生成失败，请检查网络连接或后端服务状态");
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center text-slate-500">
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
            className="text-sky-600 hover:underline"
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
        className="btn-ghost mb-6"
      >
        &larr; 返回列表
      </button>

      {/* Header */}
      <h1 className="page-title mb-4">
        {detail.title || "无标题"}
      </h1>

      {/* Meta badges */}
      <div className="flex flex-wrap gap-2 mb-6">
        <span className="secondary-chip">
          {typeLabel(detail.question_type)}
        </span>
        <span className="primary-chip">
          {domainLabel(detail.domain_type)}
        </span>
        <span
          className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${difficultyColor(detail.difficulty_level)}`}
        >
          {difficultyText(detail.difficulty_level)}
        </span>
        {detail.difficulty_score != null && (
          <span className="secondary-chip">
            评分 {detail.difficulty_score.toFixed(1)}
          </span>
        )}
        {detail.review_status && (
          <span className="primary-chip">
            {detail.review_status}
          </span>
        )}
      </div>

      {/* Content */}
      {detail.content && (
        <section className="soft-card p-6 mb-6">
          <h2 className="section-title mb-4">题目内容</h2>
          <MarkdownContent text={detail.content} />
        </section>
      )}

      {/* Source info */}
      {(detail.source_type || detail.source_ref || detail.source_excerpt) && (
        <section className="soft-card p-6 mb-6">
          <h2 className="section-title mb-3">来源信息</h2>
          <dl className="space-y-2 text-sm">
            {detail.source_type && (
              <div className="flex gap-2">
                <dt className="text-slate-500 w-24 shrink-0">来源类型</dt>
                <dd className="text-slate-800">{detail.source_type}</dd>
              </div>
            )}
            {detail.source_ref && (
              <div className="flex gap-2">
                <dt className="text-slate-500 w-24 shrink-0">来源引用</dt>
                <dd className="text-slate-800">{detail.source_ref}</dd>
              </div>
            )}
            {detail.source_excerpt && (
              <div className="flex gap-2">
                <dt className="text-slate-500 w-24 shrink-0">原文摘录</dt>
                <dd className="text-slate-600 italic">{detail.source_excerpt}</dd>
              </div>
            )}
          </dl>
        </section>
      )}

      {/* Tags */}
      {detail.tags.length > 0 && (
        <section className="soft-card p-6 mb-6">
          <h2 className="section-title mb-3">标签</h2>
          <div className="flex flex-wrap gap-2">
            {detail.tags.map((t, i) => (
              <span
                key={i}
                className="secondary-chip"
              >
                {t.tag_name}
                {t.tag_type && <span className="text-slate-400 ml-1">({t.tag_type})</span>}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Knowledge nodes */}
      {detail.knowledge_nodes.length > 0 && (
        <section className="soft-card p-6 mb-6">
          <h2 className="section-title mb-3">知识节点</h2>
          <div className="flex flex-wrap gap-2">
            {detail.knowledge_nodes.map((n, i) => (
              <span
                key={i}
                className="primary-chip"
              >
                {n.node_name}
                {n.relation_type && (
                  <span className="text-sky-400 ml-1">[{n.relation_type}]</span>
                )}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Answer summary */}
      {detail.answer_summary && (
        <section className="soft-card p-6 mb-6">
          <h2 className="section-title mb-3">答案摘要</h2>
          <MarkdownContent text={detail.answer_summary} />
        </section>
      )}

      {/* Answer detail */}
      {detail.answer_detail && (
        <section className="soft-card p-6 mb-6">
          <h2 className="section-title mb-3">详细答案</h2>
          <MarkdownContent text={detail.answer_detail} />
        </section>
      )}

      {/* Explanation */}
      {detail.explanation && (
        <section className="soft-card p-6 mb-6">
          <h2 className="section-title mb-3">讲解</h2>
          <MarkdownContent text={detail.explanation} />
        </section>
      )}

      {/* Common pitfalls */}
      {detail.common_pitfalls && (
        <section className="soft-card p-6 mb-6">
          <h2 className="section-title mb-3">常见误区</h2>
          <MarkdownContent text={detail.common_pitfalls} />
        </section>
      )}

      {/* Generate explanation button group */}
      <section className="soft-card p-6 mb-6">
        <h2 className="section-title mb-4">AI 讲解</h2>
        <p className="text-sm text-slate-500 mb-3">流式生成（实时输出）</p>
        <div className="flex flex-wrap gap-3 mb-4">
          {([
            { value: "brief", label: "简要" },
            { value: "standard", label: "标准" },
            { value: "deep", label: "深入" },
          ] as const).map(({ value, label }) => {
            const isStreaming = streamingDepth === value && streamConnected && !streamingComplete;
            const isDone = streamingDepth === value && streamingComplete;
            return (
              <button
                key={value}
                onClick={() => handleGenerate(value)}
                disabled={isStreaming || generating}
                className={isStreaming || isDone ? "btn-primary" : "btn-secondary"}
              >
                {isStreaming ? "流式中..." : isDone ? "已完成" : generating ? "启动中..." : label}
              </button>
            );
          })}
        </div>

        {generateError && (
          <div className="error-banner">
            {generateError}
          </div>
        )}

        {/* Streaming output area */}
        {streamingTaskId && (
          <div className="mt-4 p-4 rounded-lg bg-slate-50 border border-slate-200">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-slate-700">
                实时输出
                {streamPhase && <span className="text-slate-400 ml-2">阶段: {streamPhase}</span>}
              </span>
              {!streamingComplete && streamConnected && (
                <span className="text-xs text-slate-400 animate-pulse">流式中...</span>
              )}
              {streamingComplete && (
                <span className="text-xs text-green-600">完成</span>
              )}
            </div>
            {/* Progress bar */}
            <div className="w-full bg-slate-200 rounded-full h-1.5 mb-3">
              <div
                className="bg-sky-500 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${Math.max(0, Math.min(100, (streamProgress ?? 0) * 100))}%` }}
              />
            </div>
            {/* Accumulated content */}
            {accumulatedContent ? (
              <div className="whitespace-pre-wrap text-sm text-slate-800 max-h-96 overflow-y-auto p-3 bg-white rounded border border-slate-100">
                <MarkdownContent text={accumulatedContent} />
              </div>
            ) : (
              <div className="text-sm text-slate-400 text-center py-4">
                等待输出...
              </div>
            )}
          </div>
        )}
      </section>

      {/* Generated explanation */}
      {generatedExplanation && (
        <section className="soft-card p-6 mb-6">
          <h2 className="section-title mb-3">
            AI 讲解
            {generateDepth && (
              <span className="section-hint">
                （{generateDepth === "brief" ? "简要" : generateDepth === "standard" ? "标准" : "深入"}）
              </span>
            )}
          </h2>
          <MarkdownContent text={generatedExplanation} />
        </section>
      )}
    </div>
  );
}
