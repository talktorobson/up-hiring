import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

import { Providers } from "@/components/providers";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { userId, orgId } = await auth();

  if (!userId) redirect("/sign-in");
  // Sem org ativa não há tenant — manda escolher/criar. /select-org fica fora
  // deste grupo justamente pra não cair em loop de redirect.
  if (!orgId) redirect("/select-org");

  return <Providers>{children}</Providers>;
}
