"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import axios from "axios";
import QuestionCard from "@/components/QuestionCard";
import LoadingState from "@/components/LoadingState";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import Pagination from "@/components/Pagination";

interface Question {
  id: string;
  title: string;
  question_type: string | null;
  domain_type: string | null;
  difficulty_level: number | null;
  source_type?: string;
}

interface ListResponse {
  items: Question[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const PAGE_SIZE_OPTIONS = [10, 20, 50];
const DEFAULT_PAGE_SIZE = 20;

const DOMAINS = [
  "RAG", "Backend", "Frontend", "Database", "DevOps", "Algorithm", "ML",
];

const SOURCES: { value: string; label: string }[] = [
  { value: "resume", label: "简历生成" },
  { value: "file", label: "文件导入" },
  { value: "text", label: "文本导入" },
  { value: "manual", label: "手动录入" },
  { value: "ai", label: "AI 生成" },
];

export default function QuestionsPageClient() {
  const searchParams = useSearchParams();

  // Data
  const [questions, setQuestions] = useState<Question[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  // Search
  const [searchQuery, setSearchQuery] = useState("");

  // Filters
  const [domainFilter, setDomainFilter] = useState("");
  const [difficultyFilter, setDifficultyFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");

  // Quick filters
  const [resumeOnly, setResumeOnly] = useState(false);

  // ── Initialize from URL params ──────────────────────────────

  useEffect(() => {
    const src = searchParams.get("source");
    if (src === "resume") {
      setResumeOnly(true);
      setSourceFilter("resume");
    }
  }, [searchParams]);

  // ── Fetch ───────────────────────────────────────────────────

  const fetchQuestions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (searchQuery.trim()) {
        const res = await axios.get<ListResponse>("/api/v1/questions/search", {
          params: { q: searchQuery.trim(), limit: 100 },
        });
        setQuestions(res.data.items);
        setTotal(res.data.total);
      } else {
        const params: Record<string, string | number> = {
          page,
          page_size: pageSize,
        };
        if (domainFilter) params.domain_type = domainFilter;
        if (difficultyFilter) params.difficulty_level = parseInt(difficultyFilter, 10);
        if (sourceFilter) params.source_type = sourceFilter;

        const res = await axios.get<ListResponse>("/api/v1/questions", { params });
        setQuestions(res.data.items);
        setTotal(res.data.total);
      }
    } catch {
      setError("获取题目失败，请确保后端服务正在运行");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, searchQuery, domainFilter, difficultyFilter, sourceFilter]);

  useEffect(() => {
    fetchQuestions();
  }, [fetchQuestions]);

  // ── Handlers ────────────────────────────────────────────────

  const clearFilters = () => {
    setDomainFilter("");
    setDifficultyFilter("");
    setSourceFilter("");
    setResumeOnly(false);
  };

  const toggleResumeOnly = () => {
    const next = !resumeOnly;
    setResumeOnly(next);
    setSourceFilter(next ? "resume" : "");
    setPage(1);
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    setPage(1);
  };

  const hasActiveFilters = !!(domainFilter || difficultyFilter || sourceFilter || resumeOnly);

  // ── Render ──────────────────────────────────────────────────

  if (loading && questions.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <LoadingState variant="skeleton" count={5} />
      </div>
    );
  }

  if (error && questions.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <ErrorState message={error} onRetry={fetchQuestions} />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-gray-900">
          题目列表
          <span className="ml-3 text-lg font-normal text-gray-500">
            共 {total} 道
          </span>
        </h1>
        <Link
          href="/import"
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          导入题目
        </Link>
      </div>

      {/* Search */}
      <div className="bg-white rounded-lg shadow-sm border p-4 mb-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            fetchQuestions();
          }}
          className="flex gap-3"
        >
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索题目标题或内容关键词…"
            className="flex-1 border border-gray-300 rounded-md px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
          />
          <button
            type="submit"
            className="bg-blue-600 text-white px-6 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            搜索
          </button>
          {searchQuery && (
            <button
              type="button"
              onClick={() => {
                setSearchQuery("");
                setPage(1);
                fetchQuestions();
              }}
              className="text-sm text-gray-600 hover:text-gray-800 transition-colors px-3"
            >
              清除
            </button>
          )}
        </form>
      </div>

      {/* Quick filters */}
      <div className="bg-white rounded-lg shadow-sm border p-4 mb-4 flex gap-3 flex-wrap items-center">
        <button
          onClick={toggleResumeOnly}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            resumeOnly
              ? "bg-rose-100 text-rose-700 border border-rose-200"
              : "bg-gray-100 text-gray-600 border border-gray-200 hover:bg-gray-200"
          }`}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          仅看简历题
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border p-4 mb-6 flex gap-4 flex-wrap items-center">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">来源:</label>
          <select
            value={sourceFilter}
            onChange={(e) => {
              setSourceFilter(e.target.value);
              setPage(1);
            }}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
          >
            <option value="">全部</option>
            {SOURCES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">领域:</label>
          <select
            value={domainFilter}
            onChange={(e) => {
              setDomainFilter(e.target.value);
              setPage(1);
            }}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
          >
            <option value="">全部</option>
            {DOMAINS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">难度:</label>
          <select
            value={difficultyFilter}
            onChange={(e) => {
              setDifficultyFilter(e.target.value);
              setPage(1);
            }}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
          >
            <option value="">全部</option>
            <option value="1">1 - 入门</option>
            <option value="2">2 - 简单</option>
            <option value="3">3 - 中等</option>
            <option value="4">4 - 困难</option>
            <option value="5">5 - 专家</option>
          </select>
        </div>

        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
          >
            清除筛选
          </button>
        )}
      </div>

      {/* Error banner (inline, doesn't replace content) */}
      {error && (
        <div className="mb-4">
          <ErrorState message={error} onRetry={fetchQuestions} />
        </div>
      )}

      {/* Questions list */}
      {questions.length === 0 ? (
        <EmptyState
          title={hasActiveFilters ? "没有匹配的题目" : "暂无题目"}
          description={
            hasActiveFilters
              ? "尝试调整筛选条件，或导入新的题目"
              : "请先导入或添加题目"
          }
          actionLabel={hasActiveFilters ? "清除筛选" : "导入题目"}
          actionHref={hasActiveFilters ? undefined : "/import"}
          onAction={hasActiveFilters ? clearFilters : undefined}
        />
      ) : (
        <div className="space-y-4">
          <div className="grid gap-4">
            {questions.map((q) => (
              <QuestionCard key={q.id} question={q} />
            ))}
          </div>

          {/* Pagination */}
          {total > pageSize && !searchQuery && (
            <Pagination
              currentPage={page}
              pageSize={pageSize}
              total={total}
              onPageChange={handlePageChange}
              onPageSizeChange={handlePageSizeChange}
              pageSizeOptions={PAGE_SIZE_OPTIONS}
            />
          )}
        </div>
      )}
    </div>
  );
}
