import Link from "next/link";
import { GitCompare } from "lucide-react";
import type { Measurement } from "@/lib/api/types";
import { fieldLabel } from "@/lib/labels";
import { TD_CLASS, TH_CLASS, TableShell } from "@/components/ui/table-shell";
import { ComparisonStateBadge, ServingStateBadge } from "./state-badge";
import { UnitLabel, ValueKindBadge } from "./unit-label";

export function MeasurementTable({
  measurements,
  showDataset = false,
}: {
  measurements: Measurement[];
  showDataset?: boolean;
}) {
  return (
    <TableShell caption="Registered measurements with units, value kinds, serving states, and comparison states">
      <thead>
        <tr>
          <th scope="col" className={TH_CLASS}>Measurement</th>
          {showDataset ? <th scope="col" className={TH_CLASS}>Dataset</th> : null}
          <th scope="col" className={TH_CLASS}>Unit</th>
          <th scope="col" className={TH_CLASS}>Value kind</th>
          <th scope="col" className={TH_CLASS}>Comparison</th>
          <th scope="col" className={TH_CLASS}>Serving</th>
          <th scope="col" className={TH_CLASS}>Restrictions</th>
          <th scope="col" className={TH_CLASS}><span className="sr-only">Actions</span></th>
        </tr>
      </thead>
      <tbody>
        {measurements.map((measurement) => (
          <tr key={measurement.measurement_id} className="hover:bg-surface-2/35">
            <td className={TD_CLASS}>
              <p className="font-medium text-foreground">{fieldLabel(measurement.parameter)}</p>
              <p className="mt-0.5 break-all font-mono text-[10px] text-muted-2">
                {measurement.measurement_id}
              </p>
            </td>
            {showDataset ? (
              <td className={TD_CLASS}>
                <Link
                  href={`/datasets/${encodeURIComponent(measurement.dataset_id)}`}
                  className="text-accent-strong hover:text-accent-strong focus-ring"
                >
                  {measurement.dataset_id}
                </Link>
              </td>
            ) : null}
            <td className={TD_CLASS}>
              <UnitLabel unit={measurement.unit} status={measurement.unit_status} />
            </td>
            <td className={TD_CLASS}>
              <ValueKindBadge valueKind={measurement.value_kind} />
            </td>
            <td className={TD_CLASS}>
              <ComparisonStateBadge status={measurement.comparison_status} />
            </td>
            <td className={TD_CLASS}>
              <ServingStateBadge state={measurement.serving_state} />
            </td>
            <td className={TD_CLASS}>
              {measurement.quality_restrictions.length > 0 ? (
                <ul className="flex max-w-52 flex-wrap gap-1">
                  {measurement.quality_restrictions.map((restriction) => (
                    <li
                      key={restriction}
                      className="rounded border border-border-strong bg-surface-2/70 px-1.5 py-0.5 font-mono text-[10px] text-muted"
                    >
                      {restriction}
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="text-muted-2">—</span>
              )}
            </td>
            <td className={TD_CLASS}>
              <Link
                href={`/compare?left=${encodeURIComponent(measurement.measurement_id)}`}
                className="inline-flex items-center gap-1 whitespace-nowrap text-[11px] text-accent-strong hover:text-accent-strong focus-ring"
                aria-label={`Compare ${measurement.measurement_id} in Comparison Studio`}
              >
                <GitCompare className="size-3" aria-hidden="true" />
                Compare
              </Link>
            </td>
          </tr>
        ))}
      </tbody>
    </TableShell>
  );
}
