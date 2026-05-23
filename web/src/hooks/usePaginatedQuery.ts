import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";

export interface PaginatedData<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface UsePaginatedQueryOptions<T = unknown> {
  url: string;
  filters?: Record<string, string | number | boolean | undefined>;
  pageSize?: number;
  enabled?: boolean;
  onDataTransform?: (data: PaginatedData<unknown>) => PaginatedData<T>;
}

export function usePaginatedQuery<T = unknown>(
  options: UsePaginatedQueryOptions<T>
) {
  const { url, filters = {}, pageSize = 20, enabled = true } = options;

  const [data, setData] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [currentPageSize, setPageSizeState] = useState(pageSize);

  // Track filters to detect changes and reset page
  const prevFiltersRef = useRef(filters);

  useEffect(() => {
    // When filters change (search, sort, etc), reset to page 1
    if (JSON.stringify(filters) !== JSON.stringify(prevFiltersRef.current)) {
      setPage(1);
      prevFiltersRef.current = filters;
    }
  }, [filters]);

  const fetchData = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | boolean> = {
        page,
        page_size: currentPageSize,
      };
      for (const [key, value] of Object.entries(filters)) {
        if (value !== undefined && value !== "") {
          const v: string | number | boolean =
            typeof value === "boolean" ? value : String(value);
          params[key] = v;
        }
      }
      const res = await axios.get<PaginatedData<T>>(url, { params });
      const result = options.onDataTransform
        ? options.onDataTransform(res.data)
        : res.data;
      setData(result.items);
      setTotal(result.total);
      setTotalPages(result.total_pages);
    } catch (e: unknown) {
      const message =
        axios.isAxiosError(e) && e.response?.data?.detail
          ? e.response.data.detail
          : "Failed to fetch data";
      setError(String(message));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, currentPageSize, url, enabled]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const setTotalItems = (t: number) => {
    setTotal(t);
    setTotalPages(currentPageSize > 0 ? Math.ceil(t / currentPageSize) : 0);
  };

  const resetPage = () => setPage(1);

  const changePageSize = (s: number) => {
    setPageSizeState(s);
    setPage(1);
  };

  return {
    data,
    loading,
    error,
    pagination: {
      page,
      pageSize: currentPageSize,
      total,
      totalPages,
      setPage,
      setPageSize: changePageSize,
      resetPage,
      setTotal: setTotalItems,
    },
    refetch: fetchData,
  };
}
