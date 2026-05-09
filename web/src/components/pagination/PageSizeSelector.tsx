export interface PageSizeSelectorProps {
  pageSize: number;
  pageSizeOptions: number[];
  onChange: (size: number) => void;
}

export default function PageSizeSelector({
  pageSize,
  pageSizeOptions,
  onChange,
}: PageSizeSelectorProps) {
  return (
    <select
      value={pageSize}
      onChange={(e) => onChange(Number(e.target.value))}
      className="border border-gray-300 rounded px-2 py-1 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
    >
      {pageSizeOptions.map((s) => (
        <option key={s} value={s}>
          {s} 条/页
        </option>
      ))}
    </select>
  );
}
