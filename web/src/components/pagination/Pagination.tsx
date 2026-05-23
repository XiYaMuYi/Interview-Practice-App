"use client";

import { useCallback, useMemo, useState } from "react";
import PageSizeSelector from "./PageSizeSelector";
import PaginationSummary from "./PaginationSummary";

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
  pageSizeOptions = [10, 20, 30, 50],
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const [jumpInput, setJumpInput] = useState("");

  const handleJump = useCallback(() => {
    const p = parseInt(jumpInput, 10);
    if (!isNaN(p) && p >= 1 && p <= totalPages) {
      onPageChange(p);
      setJumpInput("");
    }
  }, [jumpInput, totalPages, onPageChange]);

  const handleJumpKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") handleJump();
    },
    [handleJump]
  );

  const btnClass = (active: boolean, disabled: boolean) =>
    `px-3 py-1.5 text-sm rounded border transition-colors ${
      active
        ? "bg-blue-600 text-white border-blue-600"
        : disabled
          ? "border-gray-200 text-gray-300 cursor-not-allowed"
          : "border-gray-300 hover:bg-gray-50 text-gray-700"
    }`;

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

  // Hide pagination when there's only one page and no items
  if (total === 0 && totalPages <= 1) return null;

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t">
      <div className="flex items-center gap-3 flex-wrap">
        <PaginationSummary total={total} page={currentPage} pageSize={pageSize} />
        {onPageSizeChange && (
          <PageSizeSelector
            pageSize={pageSize}
            pageSizeOptions={pageSizeOptions}
            onChange={onPageSizeChange}
          />
        )}
      </div>

      <div className="flex items-center gap-1">
        {/* Desktop: full pagination controls */}
        <nav className="hidden sm:flex items-center gap-1">
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

        {/* Mobile: simplified prev/next + page info */}
        <nav className="flex sm:hidden items-center gap-2 text-sm">
          <button
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage <= 1}
            className={btnClass(false, currentPage <= 1)}
          >
            上一页
          </button>
          <span className="text-gray-500">
            {currentPage} / {totalPages}
          </span>
          <button
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
            className={btnClass(false, currentPage >= totalPages)}
          >
            下一页
          </button>
        </nav>

        {/* Jump to page input (desktop only) */}
        <div className="hidden sm:flex items-center gap-1 ml-2 text-sm text-gray-600">
          <span>跳至</span>
          <input
            type="number"
            min={1}
            max={totalPages}
            value={jumpInput}
            onChange={(e) => setJumpInput(e.target.value)}
            onKeyDown={handleJumpKeyDown}
            className="w-14 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            placeholder="页码"
          />
          <button
            onClick={handleJump}
            disabled={!jumpInput || totalPages <= 1}
            className={`px-2 py-1 text-sm rounded border transition-colors ${
              !jumpInput || totalPages <= 1
                ? "border-gray-200 text-gray-300 cursor-not-allowed"
                : "border-gray-300 hover:bg-gray-50 text-gray-700"
            }`}
          >
            跳转
          </button>
        </div>
      </div>
    </div>
  );
}
