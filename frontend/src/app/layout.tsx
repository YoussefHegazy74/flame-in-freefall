import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import Script from "next/script";
import "./globals.css";
import { AppShell } from "@/components/layout/app-shell";
import { Providers } from "@/components/providers";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "FLAREX — Microgravity Combustion Intelligence",
    template: "%s · FLAREX",
  },
  description:
    "FLAREX — Microgravity Combustion Intelligence. Explore curated NASA PSI microgravity combustion experiments with backend-enforced serving states, comparability decisions, quality warnings, and source provenance.",
  applicationName: "FLAREX",
  authors: [{ name: "Team AFAQ" }],
  openGraph: {
    title: "FLAREX — Microgravity Combustion Intelligence",
    description:
      "A read-only evidence explorer for curated NASA PSI microgravity combustion experiments.",
    siteName: "FLAREX",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "FLAREX — Microgravity Combustion Intelligence",
    description:
      "A read-only evidence explorer for curated NASA PSI microgravity combustion experiments.",
  },
  robots: { index: false, follow: false },
  icons: {
    icon: "/icon.svg",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FFFFFF" },
    { media: "(prefers-color-scheme: dark)", color: "#0F1115" },
  ],
  colorScheme: "light dark",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Script id="flame-theme-init" strategy="beforeInteractive">
          {`(function(){try{var k="flame-theme",s=localStorage.getItem(k),d=s==="dark"||(s!=="light"&&window.matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.dataset.theme=d?"dark":"light";document.documentElement.style.colorScheme=d?"dark":"light";}catch(e){}})();`}
        </Script>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
