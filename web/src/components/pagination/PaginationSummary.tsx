export interface PaginationSummaryProps {
  total: number;
  page: number;
  pageSize: number;
}

export default function PaginationSummary({
  total,
  page,
  pageSize,
}: PaginationSummaryProps) {
  const startItem = Math.min((page - 1) * pageSize + 1, total);
  const endItem = Math.min(page * pageSize, total);

  if (total === 0) return <span className="text-sm text-gray-500">共 0 条</span>;

  return (
    <span className="text-sm text-gray-500">
      第 {startItem}–{endItem} 条，共 {total} 条
    </span>
  );
}
