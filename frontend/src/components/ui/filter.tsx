import type { ReactNode } from "react";
import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { buttonStyles } from "./button";

export function FilterBar({
  children,
  actions,
  className,
  label = "Filters",
}: {
  children: ReactNode;
  actions?: ReactNode;
  className?: string;
  label?: string;
}) {
  return (
    <section
      aria-label={label}
      className={cn("surface-flat p-4", className)}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{children}</div>
      {actions ? <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-navy-700/60 pt-3">{actions}</div> : null}
    </section>
  );
}

const CONTROL_CLASS =
  "h-9 w-full rounded-lg border border-navy-700 bg-navy-950/70 px-2.5 text-xs text-ink-100 placeholder:text-ink-500 focus:border-cyan-400/60 focus-ring";

export function TextFilter({
  id,
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  min,
  max,
  step,
  hint,
  list,
  disabled,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: "text" | "search" | "number" | "date";
  min?: number;
  max?: number;
  step?: number;
  hint?: string;
  list?: string;
  disabled?: boolean;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-[11px] font-medium text-ink-300">
        {label}
      </label>
      <div className="relative">
        {type === "search" ? (
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-500"
            aria-hidden="true"
          />
        ) : null}
        <input
          id={id}
          type={type}
          value={value}
          min={min}
          max={max}
          step={step}
          list={list}
          disabled={disabled}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          className={cn(CONTROL_CLASS, type === "search" && "pl-8", disabled && "opacity-50")}
        />
      </div>
      {hint ? <p className="mt-1 text-[10px] leading-relaxed text-ink-500">{hint}</p> : null}
    </div>
  );
}

export function SelectFilter({
  id,
  label,
  value,
  onChange,
  options,
  placeholder = "All",
  hint,
  disabled,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  placeholder?: string;
  hint?: string;
  disabled?: boolean;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-[11px] font-medium text-ink-300">
        {label}
      </label>
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className={cn(CONTROL_CLASS, "appearance-none disabled:opacity-50")}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint ? <p className="mt-1 text-[10px] leading-relaxed text-ink-500">{hint}</p> : null}
    </div>
  );
}

export function CheckboxFilter({
  id,
  label,
  checked,
  onChange,
  hint,
}: {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  hint?: string;
}) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-navy-700/70 bg-navy-950/50 p-2.5">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 size-4 rounded border-navy-500 bg-navy-900 text-cyan-400 focus:ring-cyan-400"
      />
      <div>
        <label htmlFor={id} className="cursor-pointer text-[11px] font-medium text-ink-200">
          {label}
        </label>
        {hint ? <p className="mt-0.5 text-[10px] leading-relaxed text-ink-500">{hint}</p> : null}
      </div>
    </div>
  );
}

export function FilterActions({
  onClear,
  children,
  resultLabel,
}: {
  onClear: () => void;
  children?: ReactNode;
  resultLabel?: string;
}) {
  return (
    <>
      {resultLabel ? (
        <p className="text-[11px] text-ink-400" aria-live="polite">
          {resultLabel}
        </p>
      ) : null}
      <div className="ml-auto flex flex-wrap items-center gap-2">
        {children}
        <button type="button" onClick={onClear} className={buttonStyles({ variant: "ghost", size: "sm" })}>
          <X className="size-3.5" aria-hidden="true" />
          Clear filters
        </button>
      </div>
    </>
  );
}
