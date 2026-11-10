import {
  Activity,
  BookOpen,
  Cloud,
  Database,
  Droplets,
  FileSearch,
  Flame,
  FlaskConical,
  GitCompare,
  LayoutDashboard,
  Search,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  description: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Overview",
    items: [
      {
        label: "Overview",
        href: "/",
        icon: LayoutDashboard,
        description: "Platform status, data counts, and entry points",
      },
    ],
  },
  {
    label: "Research catalog",
    items: [
      {
        label: "Investigations",
        href: "/investigations",
        icon: Search,
        description: "NASA PSI investigation catalog",
      },
      {
        label: "Datasets",
        href: "/datasets",
        icon: Database,
        description: "Curated datasets and serving states",
      },
    ],
  },
  {
    label: "Experiment explorers",
    items: [
      {
        label: "Gas Flame",
        href: "/experiments/gas-flame",
        icon: Flame,
        description: "PSI-10 and PSI-159 summary tables",
      },
      {
        label: "Materials",
        href: "/experiments/materials",
        icon: FlaskConical,
        description: "PSI-25 and PSI-26 as-run matrices",
      },
      {
        label: "Droplets",
        href: "/experiments/droplets",
        icon: Droplets,
        description: "PSI-69 FLEX droplet tests",
      },
    ],
  },
  {
    label: "Time series",
    items: [
      {
        label: "Telemetry",
        href: "/telemetry",
        icon: Activity,
        description: "PSI-100 SAFFIRE-III runs and channels",
      },
      {
        label: "Smoke",
        href: "/smoke",
        icon: Cloud,
        description: "PSI-101 SAME-R runs and channels",
      },
    ],
  },
  {
    label: "Analysis",
    items: [
      {
        label: "Research Assistant",
        href: "/assistant",
        icon: Sparkles,
        description: "Grounded answers with deterministic numbers and citations",
      },
      {
        label: "Comparison Studio",
        href: "/compare",
        icon: GitCompare,
        description: "Backend-approved measurement comparisons",
      },
      {
        label: "Data Quality",
        href: "/quality",
        icon: ShieldCheck,
        description: "Warnings, restrictions, and limitations",
      },
      {
        label: "Provenance",
        href: "/provenance",
        icon: FileSearch,
        description: "Source files, rows, and checksums",
      },
    ],
  },
  {
    label: "Reference",
    items: [
      {
        label: "Publications",
        href: "/publications",
        icon: BookOpen,
        description: "Registry-verified investigation publications",
      },
      {
        label: "Methods",
        href: "/about",
        icon: BookOpen,
        description: "Methods, limitations, and project scope",
      },
    ],
  },
];

export const NAV_ITEMS = NAV_GROUPS.flatMap((group) => group.items);

export const ROUTE_LABELS: Record<string, string> = {
  investigations: "Investigations",
  datasets: "Datasets",
  experiments: "Experiments",
  "gas-flame": "Gas Flame",
  materials: "Materials",
  droplets: "Droplets",
  telemetry: "Telemetry",
  smoke: "Smoke",
  compare: "Comparison Studio",
  assistant: "Research Assistant",
  quality: "Data Quality",
  provenance: "Provenance",
  publications: "Publications",
  about: "Methods",
};
