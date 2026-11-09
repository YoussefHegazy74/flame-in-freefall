"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

type ParamValue = string | number | boolean | null | undefined;

export interface UrlState {
  searchParams: URLSearchParams;
  get: (key: string, fallback?: string) => string | undefined;
  getNumber: (key: string) => number | undefined;
  setParams: (
    updates: Record<string, ParamValue>,
    options?: { resetOffset?: boolean; scroll?: boolean },
  ) => void;
  clearParams: (keys?: string[]) => void;
}

/**
 * URL-synchronised filter state. Every explorer keeps its filters in the query
 * string so a view can be shared, reloaded, and tested deterministically.
 */
export function useUrlState(): UrlState {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const get = useCallback(
    (key: string, fallback?: string) => searchParams.get(key) ?? fallback,
    [searchParams],
  );

  const getNumber = useCallback(
    (key: string) => {
      const value = searchParams.get(key);
      if (value === null || value.trim() === "") return undefined;
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : undefined;
    },
    [searchParams],
  );

  const setParams = useCallback(
    (
      updates: Record<string, ParamValue>,
      options: { resetOffset?: boolean; scroll?: boolean } = {},
    ) => {
      const next = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === undefined || value === "") {
          next.delete(key);
        } else {
          next.set(key, String(value));
        }
      }
      if (options.resetOffset !== false) {
        next.delete("offset");
      }
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, {
        scroll: options.scroll ?? false,
      });
    },
    [pathname, router, searchParams],
  );

  const clearParams = useCallback(
    (keys?: string[]) => {
      const next = new URLSearchParams(searchParams.toString());
      if (keys) {
        for (const key of keys) next.delete(key);
      } else {
        for (const key of Array.from(next.keys())) next.delete(key);
      }
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  return useMemo(
    () => ({ searchParams, get, getNumber, setParams, clearParams }),
    [searchParams, get, getNumber, setParams, clearParams],
  );
}
