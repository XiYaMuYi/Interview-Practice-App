"use client";

import { useMemo } from "react";
import PageSizeSelector from "./pagination/PageSizeSelector";
import PaginationSummary from "./pagination/PaginationSummary";

interface PaginationProps {
  currentPage: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  pageSizeOptions?: number[];
}

export default function Pagination({
  currentPage,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50],
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const visiblePages = useMemo(() => {
    const pages: (number | "...")[] = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (currentPage > 3) pages.push("...");
      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);
      for (let i = start; i <= end; i++) pages.push(i);
      if (currentPage < totalPages - 2) pages.push("...");
      pages.push(totalPages);
    }
    return pages;
  }, [currentPage, totalPages]);

  const btnClass = (active: boolean, disabled: boolean) =>
    `px-3 py-1.5 text-sm rounded border transition-colors ${
      active
        ? "bg-blue-600 text-white border-blue-600"
        : disabled
          ? "border-gray-200 text-gray-300 cursor-not-allowed"
          : "border-gray-300 hover:bg-gray-50 text-gray-700"
    }`;

  return (
    <div className="flex items-center justify-between flex-wrap gap-4 pt-4 border-t">
      <div className="flex items-center gap-3">
        <PaginationSummary total={total} page={currentPage} pageSize={pageSize} />
        {onPageSizeChange && (
          <PageSizeSelector
            pageSize={pageSize}
            pageSizeOptions={pageSizeOptions}
            onChange={onPageSizeChange}
          />
        )}
      </div>

      <nav className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(1)}
          disabled={currentPage <= 1}
          className={btnClass(false, currentPage <= 1)}
          title="首页"
        >
          首页
        </button>
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          className={btnClass(false, currentPage <= 1)}
        >
          上一页
        </button>

        {visiblePages.map((p, i) =>
          p === "..." ? (
            <span key={`e-${i}`} className="px-2 text-gray-400">
              ...
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              className={btnClass(p === currentPage, false)}
            >
              {p}
            </button>
          )
        )}

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className={btnClass(false, currentPage >= totalPages)}
        >
          下一页
        </button>
        <button
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage >= totalPages}
          className={btnClass(false, currentPage >= totalPages)}
          title="末页"
        >
          末页
        </button>
      </nav>
    </div>
  );
}
