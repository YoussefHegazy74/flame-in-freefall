"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { buttonStyles } from "@/components/ui/button";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Application error", error);
  }, [error]);

  return (
    <div className="surface mx-auto max-w-xl p-6" role="alert">
      <span className="inline-flex rounded-xl border border-rose-400/25 bg-rose-400/10 p-3 text-rose-300">
        <AlertTriangle className="size-6" aria-hidden="true" />
      </span>
      <h1 className="mt-4 text-xl font-semibold text-ink-50">This page could not be rendered</h1>
      <p className="mt-2 text-sm leading-relaxed text-ink-300">
        The interface hit an unexpected client error. The API was not modified. Retry the page or
        return to the overview.
      </p>
      {error.digest ? (
        <p className="mt-3 font-mono text-[10px] text-ink-500">digest: {error.digest}</p>
      ) : null}
      <button type="button" onClick={reset} className={buttonStyles({ className: "mt-5" })}>
        <RefreshCw className="size-4" aria-hidden="true" />
        Retry page
      </button>
    </div>
  );
}
