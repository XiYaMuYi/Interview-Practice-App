"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import axios from "axios";
import QuestionCard from "@/components/QuestionCard";
import { LoadingState, EmptyState, ErrorState } from "@/components/states";
import { Pagination } from "@/components/pagination";
import { usePaginatedQuery } from "@/hooks/usePaginatedQuery";
import { usePagination } from "@/hooks/usePagination";
import type { PaginatedData } from "@/hooks/usePaginatedQuery";

interface Question {
  id: string;
  title: string;
  question_type: string | null;
  domain_type: string | null;
  difficulty_level: number | null;
  source_type?: string;
}

const PAGE_SIZE_OPTIONS = [10, 20, 30, 50];
const DEFAULT_PAGE_SIZE = 20;

const DOMAINS = [
  "RAG检索增强", "Agent智能体", "LangGraph工作流", "LLM应用开发", "模型微调", "Prompt工程", "向量数据库", "多模态处理", "Text-to-SQL", "OCR文档解析", "MCP协议", "Function Calling", "vLLM部署", "FastAPI后端",
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

  // Pagination state (source of truth for page/pageSize)
  const pagination = usePagination({ initialPageSize: DEFAULT_PAGE_SIZE });

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

  // ── Build filters object for usePaginatedQuery ──────────────

  const activeFilters = useMemo(() => {
    const f: Record<string, string | number | boolean> = {};
    if (domainFilter) f.domain_type = domainFilter;
    if (difficultyFilter) f.difficulty_level = parseInt(difficultyFilter, 10);
    if (sourceFilter) f.source_type = sourceFilter;
    return f;
  }, [domainFilter, difficultyFilter, sourceFilter]);

  // ── usePaginatedQuery for the main list ─────────────────────

  const isSearchMode = !!searchQuery.trim();

  const {
    data: questions,
    loading,
    error,
    pagination: queryPagination,
    refetch,
  } = usePaginatedQuery<Question>({
    url: "/api/v1/questions",
    filters: activeFilters,
    pageSize: pagination.state.pageSize,
    enabled: !isSearchMode,
    onDataTransform: (raw: PaginatedData<unknown>) => raw as PaginatedData<Question>,
  });

  // Sync pagination state from hook back to usePagination
  useEffect(() => {
    if (queryPagination.total !== pagination.state.total) {
      pagination.setTotal(queryPagination.total);
    }
  }, [queryPagination.total]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync page changes from usePagination -> usePaginatedQuery
  useEffect(() => {
    queryPagination.setPage(pagination.state.page);
  }, [pagination.state.page]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync pageSize changes from usePagination -> usePaginatedQuery
  useEffect(() => {
    queryPagination.setPageSize(pagination.state.pageSize);
  }, [pagination.state.pageSize]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Search mode (separate, non-paginated) ───────────────────

  const [searchResults, setSearchResults] = useState<Question[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const doSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    setSearchError(null);
    try {
      const res = await axios.get("/api/v1/questions/search", {
        params: { q: searchQuery.trim(), page_size: 100 },
      });
      setSearchResults(res.data.items);
    } catch {
      setSearchError("获取题目失败，请确保后端服务正在运行");
    } finally {
      setSearchLoading(false);
    }
  }, [searchQuery]);

  // ── Handlers ────────────────────────────────────────────────

  const clearFilters = () => {
    setDomainFilter("");
    setDifficultyFilter("");
    setSourceFilter("");
    setResumeOnly(false);
    pagination.resetPage();
  };

  const toggleResumeOnly = () => {
    const next = !resumeOnly;
    setResumeOnly(next);
    setSourceFilter(next ? "resume" : "");
    pagination.resetPage();
  };

  const handlePageChange = (newPage: number) => {
    pagination.setPage(newPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handlePageSizeChange = (newSize: number) => {
    pagination.setPageSize(newSize);
  };

  const handleFilterChange = <T extends string>(
    setter: (v: T) => void,
    value: T,
  ) => {
    setter(value);
    pagination.resetPage();
  };

  const hasActiveFilters = !!(domainFilter || difficultyFilter || sourceFilter || resumeOnly);

  // ── Display data ────────────────────────────────────────────

  const displayQuestions = isSearchMode ? searchResults : questions;
  const displayLoading = isSearchMode ? searchLoading : loading;
  const displayError = isSearchMode ? searchError : error;

  // ── Render ──────────────────────────────────────────────────

  if (displayLoading && displayQuestions.length === 0) {
    return (
      <div className="page-frame">
        <LoadingState variant="skeleton" count={5} />
      </div>
    );
  }

  if (displayError && displayQuestions.length === 0) {
    return (
      <div className="page-frame">
        <ErrorState message={displayError} onRetry={isSearchMode ? doSearch : refetch} />
      </div>
    );
  }

  return (
    <div className="page-frame">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="page-title">
            题目列表
          </h1>
          <p className="page-subtitle">
            共 {isSearchMode ? searchResults.length : queryPagination.total} 道
          </p>
        </div>
        <Link
          href="/import"
          className="btn-primary"
        >
          导入题目
        </Link>
      </div>

      {/* Search */}
      <div className="soft-card p-4 mb-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            pagination.resetPage();
            if (searchQuery.trim()) {
              doSearch();
            }
          }}
          className="flex gap-3"
        >
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索题目标题或内容关键词…"
            className="form-input flex-1"
          />
          <button
            type="submit"
            className="btn-primary"
          >
            搜索
          </button>
          {searchQuery && (
            <button
              type="button"
              onClick={() => {
                setSearchQuery("");
                pagination.resetPage();
              }}
              className="btn-ghost"
            >
              清除
            </button>
          )}
        </form>
      </div>

      {/* Quick filters */}
      <div className="soft-card p-4 mb-4 flex gap-3 flex-wrap items-center">
        <button
          onClick={toggleResumeOnly}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            resumeOnly
              ? "diff-5"
              : "secondary-chip"
          }`}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          仅看简历题
        </button>
      </div>

      {/* Filters */}
      <div className="soft-card p-4 mb-6 flex gap-4 flex-wrap items-center">
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-600">来源:</label>
          <select
            value={sourceFilter}
            onChange={(e) => handleFilterChange(setSourceFilter, e.target.value)}
            className="form-select"
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
          <label className="text-sm text-slate-600">领域:</label>
          <select
            value={domainFilter}
            onChange={(e) => handleFilterChange(setDomainFilter, e.target.value)}
            className="form-select"
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
          <label className="text-sm text-slate-600">难度:</label>
          <select
            value={difficultyFilter}
            onChange={(e) => handleFilterChange(setDifficultyFilter, e.target.value)}
            className="form-select"
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
            className="btn-ghost"
          >
            清除筛选
          </button>
        )}
      </div>

      {/* Error banner (inline, doesn't replace content) */}
      {displayError && (
        <div className="mb-4">
          <ErrorState message={displayError} onRetry={isSearchMode ? doSearch : refetch} />
        </div>
      )}

      {/* Questions list */}
      {displayQuestions.length === 0 ? (
        <EmptyState
          title={hasActiveFilters || isSearchMode ? "没有匹配的题目" : "暂无题目"}
          description={
            hasActiveFilters || isSearchMode
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
            {displayQuestions.map((q) => (
              <QuestionCard key={q.id} question={q} />
            ))}
          </div>

          {/* Pagination */}
          {!isSearchMode && queryPagination.total > pagination.state.pageSize && (
            <Pagination
              currentPage={pagination.state.page}
              pageSize={pagination.state.pageSize}
              total={queryPagination.total}
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
