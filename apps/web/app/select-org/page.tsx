import { OrganizationList } from "@clerk/nextjs";

export default function SelectOrgPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <h1 className="text-xl font-semibold text-slate-900">UpHiring</h1>
          <p className="text-sm text-slate-600">
            Escolha ou crie uma organização para continuar.
          </p>
        </div>
        <OrganizationList
          hidePersonal
          afterSelectOrganizationUrl="/jobs"
          afterCreateOrganizationUrl="/jobs"
        />
      </div>
    </main>
  );
}
