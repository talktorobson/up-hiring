"use client";

import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import type { Crumb } from "@/components/breadcrumbs";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

import { MobileWarningBanner } from "./mobile-warning-banner";
import { Sidebar, SidebarNav } from "./sidebar";
import { Topbar } from "./topbar";

const SEGMENT_LABELS: Record<string, string> = {
  jobs: "Vagas",
  candidates: "Candidatos",
  settings: "Configurações",
  organization: "Organização",
  new: "Nova vaga",
};

function deriveCrumbs(pathname: string): Crumb[] {
  const parts = pathname.split("/").filter(Boolean);
  const crumbs: Crumb[] = [];
  let acc = "";
  parts.forEach((seg, i) => {
    acc += `/${seg}`;
    const known = SEGMENT_LABELS[seg];
    const isId = !known && /[0-9a-f-]{8,}/i.test(seg);
    crumbs.push({
      label: known ?? (isId ? "Detalhe" : seg),
      href: i < parts.length - 1 ? acc : undefined,
    });
  });
  return crumbs;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const crumbs = useMemo(() => deriveCrumbs(pathname), [pathname]);

  // Fecha o drawer ao navegar.
  useEffect(() => setDrawerOpen(false), [pathname]);

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar crumbs={crumbs} onOpenDrawer={() => setDrawerOpen(true)} />
        <MobileWarningBanner />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>

      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent
          side="left"
          className="w-64 border-slate-800 bg-slate-900 p-0 text-white"
        >
          <SheetHeader className="border-b border-slate-800 p-4">
            <SheetTitle className="text-left text-lg font-bold text-white">
              UpHiring
            </SheetTitle>
          </SheetHeader>
          <SidebarNav onNavigate={() => setDrawerOpen(false)} />
        </SheetContent>
      </Sheet>
    </div>
  );
}
