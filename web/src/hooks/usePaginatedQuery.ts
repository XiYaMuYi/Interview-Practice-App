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

  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  const fetchData = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | boolean> = {
        page,
        page_size: currentPageSize,
      };
      for (const [key, value] of Object.entries(filtersRef.current)) {
        if (value !== undefined && value !== "") {
          params[key] = value;
        }
      }
      const res = await axios.get<PaginatedData<T>>(url, { params });
      const result = res.data;
      setData(result.items);
      setTotal(result.total);
      setTotalPages(result.total_pages);
    } catch {
      setError("Failed to fetch data");
    } finally {
      setLoading(false);
    }
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
