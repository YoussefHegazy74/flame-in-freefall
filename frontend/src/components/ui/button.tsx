import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "icon";

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "primary-gradient border-transparent text-accent-contrast shadow-sm hover:shadow-glow disabled:opacity-50",
  secondary:
    "border-border bg-surface text-foreground hover:border-border-strong hover:bg-surface-2 disabled:opacity-50",
  ghost:
    "border-transparent bg-transparent text-muted hover:bg-surface-2 hover:text-foreground disabled:opacity-50",
  danger:
    "border-danger/30 bg-danger-soft text-danger hover:bg-danger/15 disabled:opacity-50",
};

const SIZES: Record<ButtonSize, string> = {
  sm: "h-9 px-3.5 text-[13px]",
  md: "h-10 px-4 text-sm",
  icon: "size-9 p-0",
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
    "inline-flex items-center justify-center gap-2 rounded-lg border font-semibold transition-all duration-150 focus-ring disabled:cursor-not-allowed",
    VARIANTS[variant],
    SIZES[size],
    className,
  );
}
