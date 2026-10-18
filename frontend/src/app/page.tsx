import Link from "next/link";
import { Wordmark } from "@/components/brand/Wordmark";

const SIGN_IN_HREF = "/login";
const WRAP_CLASS = "mx-auto w-full max-w-[1200px] px-6";
const LINK_CLASS =
  "rounded text-ink hover:text-iris hover:underline hover:underline-offset-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";
const BUTTON_CLASS =
  "inline-flex min-h-[46px] items-center justify-center gap-1.5 rounded-full border border-ink px-5 py-3 text-[15px] leading-none font-medium whitespace-nowrap focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";
const INK_BUTTON_CLASS = `${BUTTON_CLASS} bg-ink text-white hover:opacity-86`;
const GHOST_BUTTON_CLASS = `${BUTTON_CLASS} bg-transparent text-ink hover:bg-ink hover:text-white`;
const HEADER_BUTTON_SIZE = "min-h-[38px] px-[18px] py-2";
const POLICY_SENTENCE_CLASS = "font-serif text-[22px] leading-[1.45] md:text-[28px]";
const STATUS_CLASS = "inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-xs leading-none font-medium whitespace-nowrap";

const SITE_NAV = [
  { href: "#policy", label: "Rules" },
  { href: "#examples", label: "Approvals" },
  { href: "#never", label: "Security" },
];

type Outcome = "paid" | "asked" | "held";

const RULE_EXAMPLES: { rule: string; payee: string; outcome: Outcome; amount: string; reason: string }[] = [
  {
    rule: "Pay on its own when it is $2,500 or less.",
    payee: "Andrés Felipe Gómez",
    outcome: "paid",
    amount: "COP 4,850,000 · $1,186",
    reason: "Listed contractor, under the limit, inside the contractors budget.",
  },
  {
    rule: "Above that, ask a person.",
    payee: "Kessler Consulting GmbH",
    outcome: "asked",
    amount: "EUR 2,950.00 · $3,437",
    reason: "Everything checked out except the amount. One tap to approve, with a note for the ledger.",
  },
  {
    rule: "Never more than $8,000.",
    payee: "Servicios Integrales del Sur",
    outcome: "held",
    amount: "CLP 8,900,000 · $9,418",
    reason: "Not even a person can approve it. Split the invoice or change the policy.",
  },
  {
    rule: "Only the payees on our list.",
    payee: "Amaz0n Web Services",
    outcome: "held",
    amount: "USD 14,800.00",
    reason: "Looks like AWS, is not AWS. The zero in the name, the domain and the bank account gave it away.",
  },
];

const OUTCOME_BADGES: Record<Outcome, { label: string; className: string }> = {
  paid: { label: "Paid", className: "bg-ink text-white" },
  asked: {
    label: "Asked you",
    className: "border border-ink bg-white text-ink before:size-1.5 before:rounded-full before:bg-ink before:content-['']",
  },
  held: { label: "Held", className: "bg-ash text-ink" },
};

const NEVER_LIST = [
  "Pay someone who is not on your list.",
  "Go past the hard cap, even with approval.",
  "Follow instructions written inside an invoice.",
  "Open a file before it is scanned for malware.",
  "Decide without writing down why.",
];

function PolicyValue({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-block rounded-full border border-ink px-3 align-[0.2em] font-sans text-[0.62em] leading-[1.7] font-medium tracking-[-0.02em] tabular-nums">
      {children}
    </span>
  );
}

export default function LandingPage() {
  return (
    <div className="bg-white text-base leading-normal text-ink">
      <div className="flex flex-wrap items-center justify-center gap-3 bg-iris px-6 py-2.5 text-center text-[13px] font-medium text-white">
        <span>New: set a monthly budget per category, not just one number for the whole company.</span>
        <a
          href="#examples"
          className="rounded-full border border-white px-3.5 py-[5px] text-[13px] hover:bg-white/14 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
        >
          Learn more <span aria-hidden>→</span>
        </a>
      </div>

      <header className="border-b border-ink/15">
        <div className={`${WRAP_CLASS} flex h-16 items-center justify-between gap-4`}>
          <Link href="/" className="rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
            <Wordmark />
          </Link>
          <nav aria-label="Site" className="hidden flex-wrap gap-7 text-[15px] md:flex">
            {SITE_NAV.map((item) => (
              <a key={item.href} href={item.href} className={LINK_CLASS}>
                {item.label}
              </a>
            ))}
          </nav>
          <div className="flex gap-2.5">
            <Link href={SIGN_IN_HREF} className={`${INK_BUTTON_CLASS} ${HEADER_BUTTON_SIZE}`}>
              Sign in
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className={`${WRAP_CLASS} flex flex-wrap items-center gap-14 py-16 md:py-22`}>
          <div className="grid flex-[1_1_420px] gap-[22px]">
            <h1 className="font-serif text-[52px] leading-[1.03] md:text-[76px]">You write the rules. It pays by them.</h1>
            <p className="max-w-[460px] text-lg text-muted">
              No scripts, no workflows to draw. A payment policy written in sentences your CFO can sign, and an agent that
              reads every bill against it.
            </p>
            <div className="flex flex-wrap gap-2.5">
              <Link href={SIGN_IN_HREF} className={INK_BUTTON_CLASS}>
                Sign in <span aria-hidden>→</span>
              </Link>
              <a href="#examples" className={GHOST_BUTTON_CLASS}>
                See an example
              </a>
            </div>
          </div>
          <article
            id="policy"
            aria-label="Example payment policy"
            className="grid flex-[1_1_520px] scroll-mt-8 gap-5 rounded-lg border border-ink px-6 py-8 md:px-11 md:py-10"
          >
            <div className="flex flex-wrap justify-between gap-2 text-[13px] text-muted">
              <span>Andescape Labs, Inc. · Payment policy</span>
              <span>Version 7</span>
            </div>
            <p className={POLICY_SENTENCE_CLASS}>
              Pay a bill on its own when it is <PolicyValue>$2,500</PolicyValue> or less.
            </p>
            <p className={POLICY_SENTENCE_CLASS}>
              Above that, ask a person, up to <PolicyValue>$8,000</PolicyValue>. Never more.
            </p>
            <p className={POLICY_SENTENCE_CLASS}>
              Spend at most <PolicyValue>$30,000</PolicyValue> a month.
            </p>
            <p className={POLICY_SENTENCE_CLASS}>
              Only pay the <PolicyValue>10 payees</PolicyValue> on our list, in <PolicyValue>7 currencies</PolicyValue>.
            </p>
            <div className="flex items-end justify-between gap-4 border-t border-ink/15 pt-4 text-[13px]">
              <span className="text-muted">Approved by Camila Rojas, Finance lead</span>
              <span className="font-serif text-[22px]">C. Rojas</span>
            </div>
          </article>
        </section>

        <section id="examples" aria-labelledby="examples-title" className={`${WRAP_CLASS} scroll-mt-8 pb-18`}>
          <h2 id="examples-title" className="mb-2 max-w-[760px] font-serif text-[38px] leading-[1.07] md:text-[56px]">
            Each sentence, on a real bill.
          </h2>
          <p className="mb-6 max-w-[560px] text-muted">
            Examples from the demo workspace, decided by the agent under the policy above.
          </p>
          {RULE_EXAMPLES.map((example) => {
            const badge = OUTCOME_BADGES[example.outcome];
            return (
              <div key={example.payee} className="flex flex-wrap items-center gap-10 border-t border-line py-14">
                <p className="flex-[1_1_440px] font-serif text-[30px] leading-[1.15] md:text-[38px]">{example.rule}</p>
                <div
                  className={`grid flex-[1_1_360px] gap-2.5 rounded-lg border bg-white px-6 py-[22px] ${example.outcome === "asked" ? "border-ink" : "border-line"}`}
                >
                  <div className="flex justify-between gap-3">
                    <span className="font-medium">{example.payee}</span>
                    <span className={`${STATUS_CLASS} ${badge.className}`}>{badge.label}</span>
                  </div>
                  <span className="tabular-nums">{example.amount}</span>
                  <span className="text-sm text-muted">{example.reason}</span>
                </div>
              </div>
            );
          })}
        </section>

        <section id="never" aria-labelledby="never-title" className="scroll-mt-8 bg-carbon py-22 text-white">
          <div className={`${WRAP_CLASS} flex flex-wrap gap-12`}>
            <h2 id="never-title" className="flex-[1_1_380px] font-serif text-[38px] leading-[1.07] md:text-[56px]">
              What it will never do.
            </h2>
            <ul className="flex-[1_1_520px]">
              {NEVER_LIST.map((item) => (
                <li key={item} className="border-t border-white/18 py-[18px] text-lg last:border-b">
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>

      <footer className="relative">
        <div
          aria-hidden
          className="absolute inset-x-0 top-0 bottom-[40%] bg-[radial-gradient(#d9d9d9_1.2px,transparent_1.4px)] bg-size-[14px_14px] opacity-60"
        />
        <div className={`${WRAP_CLASS} relative grid justify-items-center gap-10 pt-20 pb-10 text-center`}>
          <h2 className="max-w-[640px] bg-white px-3 font-serif text-[38px] leading-[1.15]">Start with four sentences.</h2>
          <Link href={SIGN_IN_HREF} className={INK_BUTTON_CLASS}>
            Sign in <span aria-hidden>→</span>
          </Link>
          <span className="text-xs text-muted">© 2026 Blinka</span>
        </div>
      </footer>
    </div>
  );
}
