import { useCallback, useMemo, useState } from "react";

export interface PaginationState {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface UsePaginationOptions {
  initialPage?: number;
  initialPageSize?: number;
  total?: number;
}

export function usePagination(opts?: UsePaginationOptions) {
  const initialPage = opts?.initialPage ?? 1;
  const initialPageSize = opts?.initialPageSize ?? 20;
  const initialTotal = opts?.total ?? 0;

  const [page, setPageState] = useState(initialPage);
  const [pageSize, setPageSizeState] = useState(initialPageSize);
  const [total, setTotalState] = useState(initialTotal);

  const totalPages = useMemo(
    () => (pageSize > 0 ? Math.ceil(total / pageSize) : 0),
    [total, pageSize]
  );

  const setPage = useCallback((p: number) => setPageState(p), []);
  const setPageSize = useCallback((s: number) => {
    setPageSizeState(s);
    setPageState(1);
  }, []);
  const resetPage = useCallback(() => setPageState(1), []);
  const setTotal = useCallback((t: number) => setTotalState(t), []);

  return {
    state: { page, pageSize, total, totalPages } as PaginationState,
    setPage,
    setPageSize,
    resetPage,
    setTotal,
  };
}
