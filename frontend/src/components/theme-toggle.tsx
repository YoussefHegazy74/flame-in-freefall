"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/components/theme-provider";
import { cn } from "@/lib/utils";

export function ThemeToggle({ className }: { className?: string }) {
  const { toggleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={cn(
        "inline-flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-muted transition-colors hover:border-border-strong hover:bg-surface-2 hover:text-foreground focus-ring",
        className,
      )}
      aria-label="Toggle color theme"
      title="Toggle light and dark mode"
    >
      <Sun className="theme-toggle-sun size-4" aria-hidden="true" />
      <Moon className="theme-toggle-moon size-4" aria-hidden="true" />
    </button>
  );
}
