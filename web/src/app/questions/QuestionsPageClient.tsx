"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import QuestionCard from "@/components/QuestionCard";
import { LoadingState, EmptyState, ErrorState } from "@/components/states";
import { Pagination } from "@/components/pagination";
import { usePaginatedQuery } from "@/hooks/usePaginatedQuery";
import { usePagination } from "@/hooks/usePagination";
import { useAuth } from "@/contexts/AuthContext";
import LoginCTA from "@/components/LoginCTA";
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

const DOMAINS: { value: string; label: string }[] = [
  { value: "Agent", label: "Agent智能体" },
  { value: "RAG", label: "RAG检索增强" },
  { value: "LangGraph", label: "LangGraph工作流" },
  { value: "LLM", label: "LLM应用开发" },
  { value: "General", label: "通用" },
  { value: "Evaluation", label: "评测与可观测性" },
  { value: "Deployment", label: "部署与工程化" },
  { value: "architecture", label: "架构设计" },
  { value: "Backend", label: "后端" },
  { value: "Frontend", label: "前端" },
  { value: "Database", label: "数据库" },
  { value: "Prompt", label: "Prompt工程" },
  { value: "OCR", label: "OCR文档解析" },
  { value: "MCP", label: "MCP协议" },
  { value: "Function Calling", label: "Function Calling" },
  { value: "Text-to-SQL", label: "Text-to-SQL" },
];

const SOURCES: { value: string; label: string }[] = [
  { value: "upload", label: "文件导入" },
  { value: "resume", label: "简历生成" },
  { value: "paste", label: "文本粘贴" },
  { value: "text", label: "文本导入" },
  { value: "manual", label: "手动录入" },
  { value: "ai", label: "AI 生成" },
];

const DIFFICULTIES: { value: string; label: string }[] = [
  { value: "1", label: "1 - 入门" },
  { value: "2", label: "2 - 简单" },
  { value: "3", label: "3 - 中等" },
  { value: "4", label: "4 - 困难" },
  { value: "5", label: "5 - 专家" },
];

interface FilterState {
  source: string;
  domain: string;
  difficulty: string;
}

const EMPTY_FILTERS: FilterState = {
  source: "",
  domain: "",
  difficulty: "",
};

export default function QuestionsPageClient() {
  const { user, isLoading: authLoading, authConfig } = useAuth();
  const isAuthEnabled = authConfig?.auth_enabled ?? true;
  const isAnonymous = !authLoading && isAuthEnabled && !user;
  const canQueryQuestions = !authLoading && (!isAuthEnabled || !!user);
  const searchParams = useSearchParams();
  const pagination = usePagination({ initialPageSize: DEFAULT_PAGE_SIZE });

  const [searchQuery, setSearchQuery] = useState("");
  const [draftFilters, setDraftFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [resumeOnly, setResumeOnly] = useState(false);

  useEffect(() => {
    if (searchParams.get("source") === "resume") {
      const resumeFilters = { ...EMPTY_FILTERS, source: "resume" };
      setResumeOnly(true);
      setDraftFilters(resumeFilters);
      setAppliedFilters(resumeFilters);
    }
  }, [searchParams]);

  const activeFilters = useMemo(() => {
    const filters: Record<string, string | number> = {};
    if (appliedFilters.domain) filters.domain_type = appliedFilters.domain;
    if (appliedFilters.difficulty) filters.difficulty_level = Number(appliedFilters.difficulty);
    if (appliedFilters.source) filters.source_type = appliedFilters.source;
    return filters;
  }, [appliedFilters]);

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
    enabled: !isSearchMode && canQueryQuestions,
    onDataTransform: (raw: PaginatedData<unknown>) => raw as PaginatedData<Question>,
  });

  useEffect(() => {
    if (queryPagination.total !== pagination.state.total) {
      pagination.setTotal(queryPagination.total);
    }
  }, [queryPagination.total]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    queryPagination.setPage(pagination.state.page);
  }, [pagination.state.page]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    queryPagination.setPageSize(pagination.state.pageSize);
  }, [pagination.state.pageSize]); // eslint-disable-line react-hooks/exhaustive-deps

  const [searchResults, setSearchResults] = useState<Question[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const doSearch = useCallback(async () => {
    if (!searchQuery.trim() || !canQueryQuestions) return;
    setSearchLoading(true);
    setSearchError(null);
    try {
      const res = await api.get("/api/v1/questions/search", {
        params: { q: searchQuery.trim(), page_size: 100 },
      });
      setSearchResults(res.data.items);
    } catch {
      setSearchError("获取题目失败，请确认后端服务正在运行");
    } finally {
      setSearchLoading(false);
    }
  }, [canQueryQuestions, searchQuery]);

  const hasDraftChanges = JSON.stringify(draftFilters) !== JSON.stringify(appliedFilters);
  const hasActiveFilters = !!(
    appliedFilters.domain ||
    appliedFilters.difficulty ||
    appliedFilters.source ||
    resumeOnly
  );

  const applyFilters = () => {
    setAppliedFilters(draftFilters);
    setResumeOnly(draftFilters.source === "resume");
    pagination.resetPage();
  };

  const clearFilters = () => {
    setDraftFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setResumeOnly(false);
    pagination.resetPage();
  };

  const toggleResumeOnly = () => {
    const next = !resumeOnly;
    const nextFilters = { ...draftFilters, source: next ? "resume" : "" };
    setResumeOnly(next);
    setDraftFilters(nextFilters);
    setAppliedFilters(nextFilters);
    pagination.resetPage();
  };

  const handlePageChange = (newPage: number) => {
    pagination.setPage(newPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handlePageSizeChange = (newSize: number) => {
    pagination.setPageSize(newSize);
  };

  const displayQuestions = isSearchMode ? searchResults : questions;
  const displayLoading = isSearchMode ? searchLoading : loading;
  const displayError = isSearchMode ? searchError : error;
  const totalCount = isSearchMode ? searchResults.length : queryPagination.total;

  if (isAnonymous) {
    return (
      <div className="page-frame">
        <LoginCTA message="登录后可浏览公共题库、搜索题目并进入练习。" />
      </div>
    );
  }

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
          <h1 className="page-title">题目列表</h1>
          <p className="page-subtitle">共 {totalCount} 道</p>
        </div>
        <Link href="/import" className="btn-primary">
          导入题目
        </Link>
      </div>

      <div className="soft-card p-4 mb-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            pagination.resetPage();
            if (searchQuery.trim()) doSearch();
          }}
          className="flex gap-3"
        >
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索题目标题或内容关键词..."
            className="form-input flex-1"
          />
          <button type="submit" className="btn-primary">
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

      {isAnonymous && (
        <LoginCTA
          variant="inline"
          message="登录后可保存学习记录、收藏题目、使用 AI 讲解"
        />
      )}

      <div className="soft-card p-4 mb-4 flex gap-3 flex-wrap items-center">
        <button
          type="button"
          onClick={toggleResumeOnly}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            resumeOnly ? "diff-5" : "secondary-chip"
          }`}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          仅看简历题
        </button>
      </div>

      <div className="soft-card p-4 mb-6">
        <div className="flex gap-4 flex-wrap items-center">
          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-600" htmlFor="source-filter">来源:</label>
            <select
              id="source-filter"
              value={draftFilters.source}
              onChange={(e) => setDraftFilters((prev) => ({ ...prev, source: e.target.value }))}
              className="form-select"
            >
              <option value="">全部</option>
              {SOURCES.map((source) => (
                <option key={source.value} value={source.value}>
                  {source.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-600" htmlFor="domain-filter">领域:</label>
            <select
              id="domain-filter"
              value={draftFilters.domain}
              onChange={(e) => setDraftFilters((prev) => ({ ...prev, domain: e.target.value }))}
              className="form-select"
            >
              <option value="">全部</option>
              {DOMAINS.map((domain) => (
                <option key={domain.value} value={domain.value}>
                  {domain.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-600" htmlFor="difficulty-filter">难度:</label>
            <select
              id="difficulty-filter"
              value={draftFilters.difficulty}
              onChange={(e) => setDraftFilters((prev) => ({ ...prev, difficulty: e.target.value }))}
              className="form-select"
            >
              <option value="">全部</option>
              {DIFFICULTIES.map((difficulty) => (
                <option key={difficulty.value} value={difficulty.value}>
                  {difficulty.label}
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            onClick={applyFilters}
            className={hasDraftChanges ? "btn-primary" : "btn-secondary"}
            disabled={!hasDraftChanges}
          >
            应用筛选
          </button>

          {hasActiveFilters && (
            <button type="button" onClick={clearFilters} className="btn-ghost">
              清除筛选
            </button>
          )}
        </div>
        <p className="text-xs text-slate-500 mt-3">
          调整筛选条件后点击“应用筛选”，列表会按当前条件重新加载。
        </p>
      </div>

      {displayError && (
        <div className="mb-4">
          <ErrorState message={displayError} onRetry={isSearchMode ? doSearch : refetch} />
        </div>
      )}

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
            {displayQuestions.map((question) => (
              <QuestionCard key={question.id} question={question} />
            ))}
          </div>

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
