"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useState } from "react";
import { Wordmark } from "@/components/brand/Wordmark";
import {
  INPUT_CLASS,
  LABEL_CLASS,
  PRIMARY_BUTTON_CLASS,
  SECONDARY_BUTTON_CLASS,
} from "@/components/settings/styles";
import { api, tokenStore } from "@/lib/api";

type AuthMode = "login" | "register";

const MODE_COPY: Record<AuthMode, { title: string; hint: string; submit: string; pending: string; toggle: string }> = {
  login: {
    title: "Inicia sesión",
    hint: "Usa el correo de tu equipo de finanzas.",
    submit: "Entrar",
    pending: "Entrando...",
    toggle: "Crear una cuenta",
  },
  register: {
    title: "Crea tu cuenta",
    hint: "La contraseña debe tener al menos 8 caracteres.",
    submit: "Crear cuenta",
    pending: "Creando cuenta...",
    toggle: "Ya tengo cuenta",
  },
};

const MIN_PASSWORD_LENGTH = 8;
const REGISTER_MODE_PARAM = "register";

export default function LoginPage() {
  return (
    <main className="grid min-h-screen md:grid-cols-2">
      <section className="hidden flex-col justify-between border-r border-line bg-panel p-10 md:flex">
        <Link href="/" className="self-start rounded focus-visible:outline-2 focus-visible:outline-accent">
          <Wordmark />
        </Link>
        <div className="flex max-w-[480px] flex-col gap-6">
          <h2 className="text-[48px] leading-[1.03] font-light tracking-[-0.96px] text-ink">
            Las facturas de hoy ya están revisadas.
          </h2>
          <p className="text-[22px] leading-[1.4] tracking-[-0.22px] text-muted">
            Entra para ver qué pagó el agente, qué frenó y qué espera tu decisión.
          </p>
        </div>
        <p className="text-xs text-muted">© 2026 Blinka</p>
      </section>
      <Suspense>
        <LoginForm />
      </Suspense>
    </main>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<AuthMode>(
    searchParams.get("mode") === REGISTER_MODE_PARAM ? "register" : "login",
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const copy = MODE_COPY[mode];

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    tokenStore.clear();
    try {
      const authenticate = mode === "login" ? api.login : api.register;
      const { access_token } = await authenticate(email, password);
      tokenStore.set(access_token);
      router.replace("/inbox");
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Error inesperado");
      setIsSubmitting(false);
    }
  }

  return (
    <section className="flex flex-col justify-center gap-8 px-4 py-12 md:px-24">
      <Link href="/" className="self-start rounded focus-visible:outline-2 focus-visible:outline-accent md:hidden">
        <Wordmark />
      </Link>
      <div className="flex flex-col gap-2">
        <h1 className="text-[32px] leading-[1.1] font-light tracking-[-0.64px] text-ink">{copy.title}</h1>
        <p className="text-sm text-muted">{copy.hint}</p>
      </div>
      <form onSubmit={submit} className="flex max-w-md flex-col gap-6">
        <label className="flex flex-col gap-2">
          <span className={LABEL_CLASS}>Correo</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className={INPUT_CLASS}
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className={LABEL_CLASS}>Contraseña</span>
          <input
            type="password"
            required
            minLength={mode === "register" ? MIN_PASSWORD_LENGTH : undefined}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className={INPUT_CLASS}
          />
        </label>
        {formError && (
          <p role="alert" className="text-sm text-danger">
            <span aria-hidden>✕ </span>
            {formError}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <button type="submit" disabled={isSubmitting} className={`${PRIMARY_BUTTON_CLASS} h-12 flex-1`}>
            {isSubmitting ? copy.pending : copy.submit}
          </button>
          <button
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setFormError(null);
            }}
            className={`${SECONDARY_BUTTON_CLASS} h-12 flex-1`}
          >
            {copy.toggle}
          </button>
        </div>
      </form>
    </section>
  );
}
