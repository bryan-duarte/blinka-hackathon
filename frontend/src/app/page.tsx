import Link from "next/link";
import { Wordmark } from "@/components/brand/Wordmark";
import { PRIMARY_BUTTON_CLASS, SECONDARY_BUTTON_CLASS } from "@/components/settings/styles";

const HERO_BUTTON_SIZE = "h-12";
const LINK_FOCUS = "rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

const FEATURES = [
  {
    label: "Leer",
    title: "Entiende cada factura",
    body: "Extrae a quién, cuánto, en qué moneda y para cuándo, con la cita exacta del documento.",
  },
  {
    label: "Decidir",
    title: "Dentro de tus límites",
    body: "Topes por pago y por mes, beneficiarios permitidos y presupuestos por categoría.",
  },
  {
    label: "Explicar",
    title: "Nada sin su porqué",
    body: "Pagó, frenó o escaló: cada resultado viene con las reglas que lo produjeron.",
  },
];

const FOOTER_LINKS = [
  { href: "/inbox", label: "Bandeja" },
  { href: "/bills", label: "Cola de revisión" },
  { href: "/settings/policy", label: "Reglas de pago" },
];

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-panel">
        <div className="mx-auto flex h-19 max-w-[1320px] items-center justify-between gap-4 px-4 md:px-10">
          <div className="flex items-center gap-8">
            <Link href="/" className={LINK_FOCUS}>
              <Wordmark />
            </Link>
            <nav aria-label="Sitio" className="hidden md:block">
              <a href="#como-funciona" className={`${LINK_FOCUS} px-3 py-2 text-sm font-normal text-nav-ink hover:text-accent`}>
                Cómo funciona
              </a>
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/login" className={`${SECONDARY_BUTTON_CLASS} px-4`}>
              Inicia sesión
            </Link>
            <Link href="/login?mode=register" className={`${PRIMARY_BUTTON_CLASS} px-4`}>
              Crea tu cuenta
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1320px] flex-1 px-4 md:px-10">
        <section className="flex max-w-[1100px] flex-col gap-8 py-16 md:py-24">
          <p className="text-xs tracking-[0.5px] text-muted uppercase">Agente de pagos para equipos de finanzas</p>
          <h1 className="max-w-[15ch] text-[36px] leading-[1.03] font-light tracking-[-0.9px] text-ink md:text-[56px] md:tracking-[-1.4px]">
            Tu agente paga las cuentas. Tú pones las reglas.
          </h1>
          <p className="max-w-[40ch] text-lg leading-[1.4] text-muted md:text-[22px] md:tracking-[-0.22px]">
            Blinka lee cada factura que llega por correo, la compara con lo acordado y decide si pagarla, frenarla o
            pedirte permiso. Cada decisión queda registrada con su porqué.
          </p>
          <div className="flex flex-wrap gap-2">
            <Link href="/login?mode=register" className={`${PRIMARY_BUTTON_CLASS} ${HERO_BUTTON_SIZE}`}>
              Crea tu cuenta
            </Link>
            <a href="#como-funciona" className={`${SECONDARY_BUTTON_CLASS} ${HERO_BUTTON_SIZE}`}>
              Cómo funciona
            </a>
          </div>
        </section>

        <section id="como-funciona" aria-label="Cómo funciona" className="scroll-mt-8 border-t border-line py-16 md:py-24">
          <div className="grid gap-6 md:grid-cols-3">
            {FEATURES.map((feature) => (
              <div key={feature.label} className="flex flex-col gap-2 py-8 md:p-8 md:first:pl-0">
                <p className="text-xs tracking-[0.5px] text-muted uppercase">{feature.label}</p>
                <h2 className="mb-2 text-[32px] leading-[1.1] font-light tracking-[-0.64px] text-ink">{feature.title}</h2>
                <p className="text-base leading-[1.4] text-nav-ink">{feature.body}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-line bg-panel">
        <div className="mx-auto grid max-w-[1320px] gap-8 px-4 py-12 md:grid-cols-[2fr_1fr] md:px-10">
          <div className="flex flex-col gap-2">
            <Wordmark />
            <p className="max-w-[32ch] text-xs text-muted">
              Agente de pagos para empresas de EE. UU. con equipos en Latinoamérica.
            </p>
          </div>
          <nav aria-label="Producto" className="flex flex-col gap-2 text-sm">
            <p className="mb-2 font-normal text-ink">Producto</p>
            {FOOTER_LINKS.map((link) => (
              <Link key={link.href} href={link.href} className={`${LINK_FOCUS} self-start text-nav-ink hover:text-accent`}>
                {link.label}
              </Link>
            ))}
          </nav>
          <p className="text-xs text-muted md:col-span-2">© 2026 Blinka</p>
        </div>
      </footer>
    </div>
  );
}
