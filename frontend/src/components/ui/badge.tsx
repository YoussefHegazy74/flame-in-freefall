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
  neutral: "border-navy-600 bg-navy-800/80 text-ink-300",
  cyan: "border-cyan-400/25 bg-cyan-400/10 text-cyan-300",
  ember: "border-ember-400/25 bg-ember-400/10 text-ember-300",
  emerald: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  amber: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  rose: "border-rose-400/25 bg-rose-400/10 text-rose-300",
  violet: "border-violet-400/25 bg-violet-400/10 text-violet-400",
  outline: "border-navy-600 bg-transparent text-ink-300",
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
