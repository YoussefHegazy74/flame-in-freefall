import { LoadingState } from "@/components/ui/states";

export default function Loading() {
  return (
    <div className="space-y-4">
      <div className="h-8 w-64 animate-pulse rounded bg-surface-2" />
      <LoadingState label="Loading the FLAREX exploration interface…" rows={4} />
    </div>
  );
}
