"use client";

import { OrganizationProfile } from "@clerk/nextjs";

import { CardSkeleton } from "@/components/skeletons";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useMe } from "@/lib/hooks";

export default function OrganizationSettingsPage() {
  const { data: me, isLoading } = useMe();

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6 lg:p-8">
      <h1 className="text-2xl font-bold tracking-tight">
        Configurações da organização
      </h1>

      {isLoading ? (
        <CardSkeleton />
      ) : me ? (
        <Card>
          <CardHeader>
            <CardTitle>Tenant interno</CardTitle>
            <CardDescription>
              Identificadores usados pela API (somente leitura).
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            <Row label="Tenant ID" value={me.tenant.id} mono />
            <Row label="Nome" value={me.tenant.name} />
            <Row label="Slug" value={me.tenant.slug} />
            <Row label="Seu papel" value={me.role} />
          </CardContent>
        </Card>
      ) : null}

      <OrganizationProfile
        routing="hash"
        appearance={{ elements: { rootBox: "w-full" } }}
      />
    </div>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b py-1.5 last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className={mono ? "font-mono text-xs" : ""}>{value}</span>
    </div>
  );
}
