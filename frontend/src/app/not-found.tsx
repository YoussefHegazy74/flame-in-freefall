import Link from "next/link";
import { FileQuestion } from "lucide-react";
import { buttonStyles } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="surface mx-auto max-w-xl p-6">
      <span className="inline-flex rounded-xl border border-navy-600 bg-navy-800/70 p-3 text-ink-300">
        <FileQuestion className="size-6" aria-hidden="true" />
      </span>
      <h1 className="mt-4 text-xl font-semibold text-ink-50">Page not found</h1>
      <p className="mt-2 text-sm leading-relaxed text-ink-300">
        This route is not part of the implemented exploration interface. Return to the overview or
        open the investigation catalog.
      </p>
      <div className="mt-5 flex flex-wrap gap-2">
        <Link href="/" className={buttonStyles({ variant: "primary" })}>
          Overview
        </Link>
        <Link href="/investigations" className={buttonStyles()}>
          Investigations
        </Link>
      </div>
    </div>
  );
}
