"use client";

import { OrganizationSwitcher, UserButton, useAuth } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { Menu } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import { Breadcrumbs, type Crumb } from "@/components/breadcrumbs";
import { Button } from "@/components/ui/button";

/**
 * Ao trocar de org o JWT muda (novo tenant). React Query não sabe disso
 * sozinho — limpamos o cache e refazemos o fetch da rota atual.
 */
function useRefreshOnOrgChange() {
  const { orgId } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const prev = useRef<string | null | undefined>(orgId);
  useEffect(() => {
    if (prev.current !== undefined && prev.current !== orgId) {
      qc.clear();
      router.refresh();
    }
    prev.current = orgId;
  }, [orgId, qc, router]);
}

export function Topbar({
  crumbs,
  onOpenDrawer,
}: {
  crumbs: Crumb[];
  onOpenDrawer: () => void;
}) {
  useRefreshOnOrgChange();
  return (
    <header className="flex h-14 items-center gap-3 border-b border-slate-800 bg-slate-900 px-4 text-white">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden text-slate-200 hover:bg-slate-800 hover:text-white"
        onClick={onOpenDrawer}
        aria-label="Abrir menu"
      >
        <Menu className="h-5 w-5" />
      </Button>

      <Link href="/jobs" className="text-lg font-bold tracking-tight">
        UpHiring
      </Link>

      <div className="hidden md:block ml-4">
        <Breadcrumbs items={crumbs} className="text-slate-400" />
      </div>

      <div className="ml-auto flex items-center gap-3">
        <OrganizationSwitcher
          hidePersonal
          afterSelectOrganizationUrl="/jobs"
          afterCreateOrganizationUrl="/jobs"
          appearance={{ elements: { rootBox: "text-white" } }}
        />
        <UserButton afterSignOutUrl="/" />
      </div>
    </header>
  );
}
