interface LoadingStateProps {
  message?: string;
  variant?: "skeleton" | "spinner" | "text";
  count?: number;
}

export default function LoadingState({
  message = "加载中...",
  variant = "skeleton",
  count = 3,
}: LoadingStateProps) {
  if (variant === "spinner") {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <span className="text-sm text-gray-500">{message}</span>
      </div>
    );
  }

  if (variant === "text") {
    return (
      <div className="text-center py-12 text-gray-500">
        <span className="text-sm">{message}</span>
      </div>
    );
  }

  return (
    <div className="space-y-4" aria-label={message}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-white rounded-lg shadow-sm border p-5 animate-pulse">
          <div className="h-5 bg-gray-200 rounded w-2/3 mb-3" />
          <div className="h-4 bg-gray-100 rounded w-1/2" />
        </div>
      ))}
      <p className="text-center text-sm text-gray-400">{message}</p>
    </div>
  );
}
