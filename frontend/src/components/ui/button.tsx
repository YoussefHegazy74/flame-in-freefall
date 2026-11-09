import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "border-cyan-400/40 bg-cyan-400 text-void hover:bg-cyan-300 disabled:bg-cyan-400/40 disabled:text-void/60",
  secondary:
    "border-navy-600 bg-navy-800/80 text-ink-100 hover:border-navy-500 hover:bg-navy-700/80 disabled:text-ink-500",
  ghost:
    "border-transparent bg-transparent text-ink-300 hover:bg-navy-800/80 hover:text-ink-50 disabled:text-ink-600",
  danger:
    "border-rose-400/40 bg-rose-400/10 text-rose-300 hover:bg-rose-400/20 disabled:text-rose-300/50",
};

const SIZES: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
};

export function buttonStyles({
  variant = "secondary",
  size = "md",
  className,
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
} = {}) {
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-lg border font-medium transition-colors focus-ring disabled:cursor-not-allowed",
    VARIANTS[variant],
    SIZES[size],
    className,
  );
}
