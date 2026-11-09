"use client";

import dynamic from "next/dynamic";
import { LoadingState } from "@/components/ui/states";

export const LazyTimeSeriesChart = dynamic(
  () => import("./time-series-chart").then((module) => module.TimeSeriesChart),
  {
    ssr: false,
    loading: () => <LoadingState label="Loading chart module…" rows={2} />,
  },
);
