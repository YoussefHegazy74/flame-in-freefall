import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type BadgeTone =
  | "neutral"
  | "cyan"
  | "ember"
  | "emerald"
  | "amber"
  | "rose"
  | "violet"
  | "outline";

const TONES: Record<BadgeTone, string> = {
  neutral: "border-border bg-surface-2 text-muted",
  cyan: "border-accent/20 bg-accent-soft text-accent-strong",
  ember: "border-warning/20 bg-warning-soft text-warning",
  emerald: "border-success/20 bg-success-soft text-success",
  amber: "border-warning/20 bg-warning-soft text-warning",
  rose: "border-danger/20 bg-danger-soft text-danger",
  violet: "border-info/20 bg-info-soft text-info",
  outline: "border-border bg-transparent text-muted",
};

export function Badge({
  children,
  tone = "neutral",
  className,
  title,
}: {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-5",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
