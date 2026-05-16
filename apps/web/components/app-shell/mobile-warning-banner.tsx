"use client";

import { Info } from "lucide-react";
import { usePathname } from "next/navigation";

/**
 * #40/#43: abaixo de md, criar/editar vaga e o Kanban pedem desktop.
 * O resto da UI (listas, candidato) funciona em qualquer tela, então o
 * banner só aparece nas rotas de vaga específica e some em md+.
 */
function needsDesktop(pathname: string): boolean {
  if (pathname === "/jobs/new") return true;
  // /jobs/<id> e subrotas (pipeline), mas não /jobs nem /jobs/new já tratado.
  return /^\/jobs\/[^/]+/.test(pathname);
}

export function MobileWarningBanner() {
  const pathname = usePathname();
  if (!needsDesktop(pathname)) return null;
  return (
    <div className="flex items-start gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800 md:hidden">
      <Info className="mt-0.5 h-4 w-4 shrink-0" />
      <p>
        Use o desktop para criar vagas e mover o pipeline. A gestão de
        candidatos funciona em qualquer tela.
      </p>
    </div>
  );
}
