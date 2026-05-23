import { useCallback, useEffect, useRef, useState } from "react";

export interface UseDebouncedSearchOptions {
  debounceMs?: number;
  minLength?: number;
  onSearch?: (query: string) => void;
}

/**
 * Debounced search input hook. Delays callback invocation until
 * the user stops typing for `debounceMs` milliseconds.
 */
export function useDebouncedSearch(opts?: UseDebouncedSearchOptions) {
  const { debounceMs = 400, minLength = 0, onSearch } = opts ?? {};

  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  // Update raw query immediately, schedule debounced update
  const updateQuery = useCallback(
    (value: string) => {
      setQuery(value);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        setDebouncedQuery(value);
      }, debounceMs);
    },
    [debounceMs]
  );

  // Fire onSearch when debounced value changes
  useEffect(() => {
    if (debouncedQuery.length >= minLength) {
      onSearch?.(debouncedQuery);
    }
  }, [debouncedQuery, minLength, onSearch]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const clear = useCallback(() => {
    setQuery("");
    setDebouncedQuery("");
  }, []);

  return {
    query,
    debouncedQuery,
    setQuery: updateQuery,
    clear,
    isSearching: query !== debouncedQuery,
  };
}
