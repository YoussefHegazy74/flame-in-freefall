import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { AppShell } from "@/components/layout/app-shell";
import { Providers } from "@/components/providers";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Flame in Freefall · NASA PSI evidence explorer",
    template: "%s · Flame in Freefall",
  },
  description:
    "Explore NASA microgravity combustion experiments with backend-enforced serving states, comparability decisions, quality warnings, and source provenance.",
  applicationName: "Flame in Freefall",
  authors: [{ name: "Team AFAQ" }],
  robots: { index: false, follow: false },
  icons: {
    icon: "/icon.svg",
  },
};

export const viewport: Viewport = {
  themeColor: "#030711",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
