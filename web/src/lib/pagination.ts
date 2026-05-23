export function calculateOffset(page: number, pageSize: number): number {
  return (page - 1) * pageSize;
}

export function calculateTotalPages(total: number, pageSize: number): number {
  return pageSize > 0 ? Math.ceil(total / pageSize) : 0;
}

export { usePagination } from "@/hooks/usePagination";
export { usePaginatedQuery } from "@/hooks/usePaginatedQuery";
export type { PaginationState } from "@/hooks/usePagination";
export type { PaginatedData, UsePaginatedQueryOptions } from "@/hooks/usePaginatedQuery";
