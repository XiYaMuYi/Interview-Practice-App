"use client";

import { useState } from "react";

export interface FilterTag {
  label: string;
  value: string;
  removable?: boolean;
}

interface FilterBarProps {
  /** Active filter tags displayed as chips */
  activeFilters?: FilterTag[];
  /** Called when a single filter chip is removed */
  onRemoveFilter?: (value: string) => void;
  /** Called when "Clear all" is clicked */
  onClearAll?: () => void;
  /** Optional inline search input */
  searchQuery?: string;
  onSearchChange?: (query: string) => void;
  onSearchSubmit?: () => void;
  searchPlaceholder?: string;
}

export default function FilterBar({
  activeFilters = [],
  onRemoveFilter,
  onClearAll,
  searchQuery,
  onSearchChange,
  onSearchSubmit,
  searchPlaceholder = "搜索…",
}: FilterBarProps) {
  const [localInput, setLocalInput] = useState(searchQuery ?? "");

  const hasFilters = activeFilters.length > 0;
  const hasSearch = onSearchChange !== undefined;

  if (!hasFilters && !hasSearch) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearchSubmit?.();
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border p-4 mb-4 space-y-3">
      {/* Search row */}
      {hasSearch && (
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            type="text"
            value={localInput}
            onChange={(e) => {
              setLocalInput(e.target.value);
              onSearchChange?.(e.target.value);
            }}
            placeholder={searchPlaceholder}
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
                setLocalInput("");
                onSearchChange?.("");
                onSearchSubmit?.();
              }}
              className="text-sm text-gray-600 hover:text-gray-800 transition-colors px-3"
            >
              清除
            </button>
          )}
        </form>
      )}

      {/* Filter chips row */}
      {hasFilters && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-gray-500">筛选:</span>
          {activeFilters.map((tag) => (
            <span
              key={tag.value}
              className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium bg-blue-50 text-blue-700 border border-blue-200"
            >
              {tag.label}
              {tag.removable !== false && onRemoveFilter && (
                <button
                  onClick={() => onRemoveFilter(tag.value)}
                  className="ml-0.5 text-blue-400 hover:text-blue-600 transition-colors"
                  aria-label={`移除 ${tag.label}`}
                >
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </span>
          ))}
          {onClearAll && (
            <button
              onClick={onClearAll}
              className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
            >
              清除筛选
            </button>
          )}
        </div>
      )}
    </div>
  );
}
