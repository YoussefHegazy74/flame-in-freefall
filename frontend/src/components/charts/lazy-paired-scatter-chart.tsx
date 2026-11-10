"use client";

import dynamic from "next/dynamic";
import { LoadingState } from "@/components/ui/states";

export const LazyPairedScatterChart = dynamic(
  () => import("./paired-scatter-chart").then((module) => module.PairedScatterChart),
  {
    ssr: false,
    loading: () => <LoadingState label="Loading paired chart module…" rows={2} />,
  },
);
