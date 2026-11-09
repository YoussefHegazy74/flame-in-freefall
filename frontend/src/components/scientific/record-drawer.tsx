"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

export function RecordDrawer({
  open,
  title,
  subtitle,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  subtitle?: ReactNode;
  onClose: () => void;
  children: ReactNode;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[70] flex justify-end">
      <div
        className="absolute inset-0 bg-void/80 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="record-drawer-title"
        className="relative flex h-full w-full max-w-2xl flex-col border-l border-navy-600 bg-navy-950 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-navy-700 px-5 py-4">
          <div className="min-w-0">
            <h2 id="record-drawer-title" className="text-base font-semibold text-ink-50">
              {title}
            </h2>
            {subtitle ? <div className="mt-1 text-xs text-ink-400">{subtitle}</div> : null}
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-lg border border-navy-600 bg-navy-900 p-2 text-ink-300 hover:text-ink-50 focus-ring"
            aria-label="Close record detail"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
      </section>
    </div>
  );
}
