import { SignInButton, SignedIn, SignedOut, UserButton } from "@clerk/nextjs";

export default function Home() {
  return (
    <main className="min-h-screen p-12 max-w-5xl mx-auto">
      <header className="flex justify-between items-center mb-12">
        <h1 className="text-2xl font-bold">UpHiring</h1>
        <div>
          <SignedOut>
            <SignInButton mode="modal">
              <button className="px-4 py-2 bg-brand-500 text-white rounded-md hover:bg-brand-700">
                Entrar
              </button>
            </SignInButton>
          </SignedOut>
          <SignedIn>
            <UserButton />
          </SignedIn>
        </div>
      </header>

      <section className="space-y-6">
        <h2 className="text-4xl font-bold tracking-tight">
          Recrutamento inteligente para empresas brasileiras
        </h2>
        <p className="text-lg text-slate-600 max-w-2xl">
          Plataforma de Applicant Tracking System feita para SME de serviços e comércio.
          Integração nativa com WhatsApp, eSocial, Idwall, Clicksign.
        </p>

        <SignedIn>
          <a
            href="/jobs"
            className="inline-block px-6 py-3 bg-brand-500 text-white rounded-md hover:bg-brand-700"
          >
            Abrir app
          </a>
        </SignedIn>
      </section>
    </main>
  );
}
