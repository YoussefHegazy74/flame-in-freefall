"use client";

import { useState, type ReactNode } from "react";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { Footer } from "./footer";

export function AppShell({ children }: { children: ReactNode }) {
  const [navOpen, setNavOpen] = useState(false);

  return (
    <div className="min-h-screen overflow-x-hidden">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <Topbar onOpenNav={() => setNavOpen(true)} />
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      <div className="lg:pl-[272px]">
        <main
          id="main-content"
          className="mx-auto w-full max-w-[1440px] px-4 pb-16 pt-7 sm:px-6 sm:pt-9 lg:px-8 lg:pt-10"
        >
          {children}
        </main>
        <Footer />
      </div>
    </div>
  );
}
