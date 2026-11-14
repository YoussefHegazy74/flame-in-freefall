import { cn } from "@/lib/utils";
import { FlarexMark } from "./flarex-mark";

export function FlarexBrand({
  className,
  markClassName,
  wordmarkClassName,
  taglineClassName,
}: {
  className?: string;
  markClassName?: string;
  wordmarkClassName?: string;
  taglineClassName?: string;
}) {
  return (
    <span className={cn("flex min-w-0 items-center gap-2.5", className)}>
      <span
        className={cn(
          "brand-mark flex size-9 shrink-0 items-center justify-center rounded-xl text-white",
          markClassName,
        )}
      >
        <FlarexMark className="size-5" />
      </span>
      <span className="min-w-0">
        <span
          className={cn(
            "block text-[13px] font-semibold uppercase leading-tight tracking-[0.16em] text-foreground",
            wordmarkClassName,
          )}
        >
          FLAREX
        </span>
        <span
          className={cn(
            "block text-[9px] font-semibold uppercase leading-tight tracking-[0.1em] text-muted",
            taglineClassName,
          )}
        >
          Microgravity Combustion Intelligence
        </span>
      </span>
    </span>
  );
}
