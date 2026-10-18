import Link from "next/link";
import { Wordmark } from "@/components/brand/Wordmark";
import { PRIMARY_BUTTON_CLASS, SECONDARY_BUTTON_CLASS } from "@/components/settings/styles";

const HERO_BUTTON_SIZE = "h-12";
const LINK_FOCUS = "rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

const FEATURES = [
  {
    label: "Read",
    title: "Understands every invoice",
    body: "Extracts who, how much, in which currency and by when, with the exact quote from the document.",
  },
  {
    label: "Decide",
    title: "Within your limits",
    body: "Per-payment and monthly caps, allowed payees and budgets per category.",
  },
  {
    label: "Explain",
    title: "Nothing without a reason",
    body: "Paid, held or escalated: every outcome comes with the rules that produced it.",
  },
];

const FOOTER_LINKS = [
  { href: "/inbox", label: "Inbox" },
  { href: "/bills", label: "Review queue" },
  { href: "/ledger", label: "Agent ledger" },
  { href: "/settings/policy", label: "Payment rules" },
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
            <nav aria-label="Site" className="hidden md:block">
              <a href="#how-it-works" className={`${LINK_FOCUS} px-3 py-2 text-sm font-normal text-nav-ink hover:text-accent`}>
                How it works
              </a>
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/login" className={`${SECONDARY_BUTTON_CLASS} px-4`}>
              Sign in
            </Link>
            <Link href="/login?mode=register" className={`${PRIMARY_BUTTON_CLASS} px-4`}>
              Create your account
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1320px] flex-1 px-4 md:px-10">
        <section className="flex max-w-[1100px] flex-col gap-8 py-16 md:py-24">
          <p className="text-xs tracking-[0.5px] text-muted uppercase">Payments agent for finance teams</p>
          <h1 className="max-w-[15ch] text-[36px] leading-[1.03] font-light tracking-[-0.9px] text-ink md:text-[56px] md:tracking-[-1.4px]">
            Your agent pays the bills. You set the rules.
          </h1>
          <p className="max-w-[40ch] text-lg leading-[1.4] text-muted md:text-[22px] md:tracking-[-0.22px]">
            Blinka reads every invoice that arrives by email, compares it with what was agreed and decides whether to
            pay it, hold it or ask you first. Every decision is recorded with its reason.
          </p>
          <div className="flex flex-wrap gap-2">
            <Link href="/login?mode=register" className={`${PRIMARY_BUTTON_CLASS} ${HERO_BUTTON_SIZE}`}>
              Create your account
            </Link>
            <a href="#how-it-works" className={`${SECONDARY_BUTTON_CLASS} ${HERO_BUTTON_SIZE}`}>
              How it works
            </a>
          </div>
        </section>

        <section id="how-it-works" aria-label="How it works" className="scroll-mt-8 border-t border-line py-16 md:py-24">
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
              Payments agent for US companies with teams in Latin America.
            </p>
          </div>
          <nav aria-label="Product" className="flex flex-col gap-2 text-sm">
            <p className="mb-2 font-normal text-ink">Product</p>
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
