import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <p className="text-5xl font-bold text-slate-300">404</p>
      <p className="text-sm text-muted-foreground">
        Página não encontrada.
      </p>
      <Button asChild>
        <Link href="/jobs">Voltar para Vagas</Link>
      </Button>
    </div>
  );
}
