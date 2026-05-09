export interface PaginationState {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface UsePaginationOptions {
  initialPage?: number;
  initialPageSize?: number;
  pageSizeOptions?: number[];
}

export function usePagination(opts?: UsePaginationOptions) {
  const initialPage = opts?.initialPage ?? 1;
  const initialPageSize = opts?.initialPageSize ?? 20;
  const pageSizeOptions = opts?.pageSizeOptions ?? [10, 20, 30, 50];

  const state: PaginationState = {
    page: initialPage,
    pageSize: initialPageSize,
    total: 0,
    totalPages: Math.ceil(0 / initialPageSize),
  };

  return {
    state,
    pageSizeOptions,
    setPage: (p: number) => {
      state.page = p;
    },
    setPageSize: (s: number) => {
      state.pageSize = s;
      state.page = 1;
    },
    resetPage: () => {
      state.page = 1;
    },
    setTotal: (t: number) => {
      state.total = t;
      state.totalPages = state.pageSize > 0 ? Math.ceil(t / state.pageSize) : 0;
    },
  };
}
