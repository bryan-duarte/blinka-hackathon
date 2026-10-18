"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { Wordmark } from "@/components/brand/Wordmark";
import { PRIMARY_BUTTON_CLASS } from "@/components/settings/styles";
import { api, tokenStore } from "@/lib/api";

const FIELD_INPUT_CLASS =
  "h-12 rounded border border-selection bg-white px-3.5 text-[15px] text-ink focus:border-ink focus:outline-2 focus:outline-offset-1 focus:outline-ink";
const STATUS_CLASS = "inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-xs leading-none font-medium whitespace-nowrap";
const PAID_STATUS_CLASS = `${STATUS_CLASS} bg-ink text-white`;
const NEEDS_STATUS_CLASS = `${STATUS_CLASS} border border-ink bg-white text-ink before:size-1.5 before:rounded-full before:bg-ink before:content-['']`;

const PREVIEW_ROWS = [
  { payee: "Amazon Web Services", amount: "$1,284", isPaid: true },
  { payee: "Andrés Felipe Gómez", amount: "$1,186", isPaid: true },
  { payee: "Kessler Consulting", amount: "$3,437", isPaid: false },
];

export default function LoginPage() {
  return (
    <main className="flex min-h-screen flex-wrap bg-white text-sm text-ink">
      <section className="flex flex-[1_1_480px] flex-col px-6 pt-8 pb-10 md:px-12">
        <Link
          href="/"
          className="self-start rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          <Wordmark />
        </Link>
        <div className="flex flex-1 items-center justify-center py-12">
          <LoginForm />
        </div>
        <p className="text-xs text-muted">Blinka never moves money without a rule that allows it.</p>
      </section>
      <ProductPreview />
    </main>
  );
}

function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    tokenStore.clear();
    try {
      const { access_token } = await api.login(email, password);
      tokenStore.set(access_token);
      router.replace("/inbox");
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Unexpected error");
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex w-full max-w-[400px] flex-col gap-5">
      <div className="mb-2 grid gap-2.5">
        <h1 className="font-serif text-[44px] leading-[1.07] md:text-[52px]">Sign in</h1>
        <p className="text-base text-muted">
          Your agent kept working while you were away. See what it paid and what it is holding for you.
        </p>
      </div>
      <div className="grid gap-1.5">
        <label htmlFor="login-email" className="text-sm font-medium">
          Work email
        </label>
        <input
          id="login-email"
          type="email"
          required
          autoComplete="email"
          placeholder="you@company.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className={FIELD_INPUT_CLASS}
        />
      </div>
      <div className="grid gap-1.5">
        <label htmlFor="login-password" className="text-sm font-medium">
          Password
        </label>
        <input
          id="login-password"
          type="password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className={FIELD_INPUT_CLASS}
        />
      </div>
      {formError && (
        <p role="alert" className="text-sm text-danger">
          <span aria-hidden>✕ </span>
          {formError}
        </p>
      )}
      <button type="submit" disabled={isSubmitting} className={`${PRIMARY_BUTTON_CLASS} h-12 w-full`}>
        {isSubmitting ? (
          "Signing in..."
        ) : (
          <>
            Sign in <span aria-hidden>→</span>
          </>
        )}
      </button>
    </form>
  );
}

function ProductPreview() {
  return (
    <section
      aria-label="Product preview"
      className="relative grid min-h-[640px] flex-[1_1_560px] place-items-center overflow-hidden bg-deep-teal p-6 md:p-12"
    >
      <svg
        viewBox="0 0 600 800"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
        className="absolute inset-0 size-full"
      >
        <defs>
          <filter id="login-wash">
            <feGaussianBlur stdDeviation="38" />
          </filter>
        </defs>
        <g filter="url(#login-wash)">
          <ellipse cx="120" cy="140" rx="260" ry="160" fill="#ffffff" fillOpacity="0.07" />
          <ellipse cx="480" cy="300" rx="200" ry="260" fill="#ffffff" fillOpacity="0.1" />
          <ellipse cx="260" cy="620" rx="320" ry="150" fill="#000000" fillOpacity="0.35" />
          <ellipse cx="520" cy="720" rx="180" ry="120" fill="#ffffff" fillOpacity="0.08" />
        </g>
      </svg>
      <div className="relative grid w-full max-w-[440px] gap-3">
        <div className="grid gap-3.5 rounded-lg bg-white px-6 py-[22px]">
          <div className="flex items-center justify-between text-xs text-muted">
            <span>Overnight</span>
            <span className="tabular-nums">07:00</span>
          </div>
          <p className="font-serif text-[28px] leading-[1.15]">Paid 4 bills. 2 are waiting for you.</p>
          <div>
            {PREVIEW_ROWS.map((row) => (
              <div
                key={row.payee}
                className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 border-t border-ash py-2.5"
              >
                <span>{row.payee}</span>
                <span className="tabular-nums">{row.amount}</span>
                <span className={row.isPaid ? PAID_STATUS_CLASS : NEEDS_STATUS_CLASS}>
                  {row.isPaid ? "Paid" : "Needs you"}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-lg bg-white px-5 py-4 md:ml-12">
          <span className="grid size-8 flex-none place-items-center rounded-full border border-ink">
            <svg
              viewBox="0 0 24 24"
              aria-hidden="true"
              className="size-4 fill-none stroke-ink stroke-[1.5]"
              strokeLinecap="round"
            >
              <circle cx="12" cy="12" r="8" />
              <path d="M12 8v5M12 16h.01" />
            </svg>
          </span>
          <span className="text-[13px] leading-[1.4]">
            <strong className="font-medium">Why it asked:</strong> $3,437 is above your $2,500 auto-pay limit.
          </span>
        </div>
      </div>
    </section>
  );
}
