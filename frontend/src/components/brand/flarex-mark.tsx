import { cn } from "@/lib/utils";

export function FlarexMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      className={cn("size-5", className)}
    >
      <ellipse
        cx="16"
        cy="16.5"
        rx="12.2"
        ry="5.6"
        transform="rotate(-28 16 16.5)"
        stroke="currentColor"
        strokeOpacity="0.34"
        strokeWidth="1.2"
      />
      <path
        d="M17.75 4.5c1.4 5.2-3.85 6.75-3.85 11.6 0 2.25 1.45 3.9 3.4 3.9 2.25 0 3.85-1.9 3.85-4.45 0-1.2-.35-2.2-1-3.35 3.2 2.05 5.35 5.1 5.35 8.75 0 5.1-3.7 8.15-8 8.15-4.75 0-9-3.65-9-10.75 0-6.15 5.7-9.85 8.75-15.75Z"
        fill="currentColor"
      />
      <path
        d="M16.85 16.1c0.95 2.45-1.5 3.4-1.5 5.65 0 1.4 1 2.45 2.3 2.45 1.45 0 2.5-1.25 2.5-2.9 0-2.45-1.65-3.75-3.3-5.2Z"
        stroke="currentColor"
        strokeOpacity="0.55"
        strokeWidth="1.1"
      />
      <circle cx="26.1" cy="9.1" r="1.25" fill="currentColor" />
      <circle cx="5.8" cy="22.7" r="0.8" fill="currentColor" fillOpacity="0.55" />
    </svg>
  );
}
