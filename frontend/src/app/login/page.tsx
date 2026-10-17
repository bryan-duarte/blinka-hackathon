"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { api, tokenStore } from "@/lib/api";

type AuthMode = "login" | "register";

const MODE_COPY: Record<AuthMode, { title: string; submit: string; toggle: string }> = {
  login: {
    title: "Ingresar",
    submit: "Ingresar",
    toggle: "¿No tienes cuenta? Crear cuenta",
  },
  register: {
    title: "Crear cuenta",
    submit: "Crear cuenta",
    toggle: "¿Ya tienes cuenta? Ingresar",
  },
};

const MIN_PASSWORD_LENGTH = 8;

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("login");
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
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <p className="text-sm font-semibold tracking-tight text-accent">Blinka Inbox</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink">{copy.title}</h1>
        <form
          onSubmit={submit}
          className="mt-6 space-y-4 rounded-lg border border-line bg-panel p-5"
        >
          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-ink">Correo</span>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="h-10 w-full rounded-md border border-line bg-panel px-3 text-sm text-ink outline-none focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/20"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-ink">Contraseña</span>
            <input
              type="password"
              required
              minLength={mode === "register" ? MIN_PASSWORD_LENGTH : undefined}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="h-10 w-full rounded-md border border-line bg-panel px-3 text-sm text-ink outline-none focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/20"
            />
          </label>
          {formError && (
            <p role="alert" className="text-sm text-danger">
              {formError}
            </p>
          )}
          <button
            type="submit"
            disabled={isSubmitting}
            className="h-10 w-full rounded-md bg-accent text-sm font-medium text-white transition-colors hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Enviando..." : copy.submit}
          </button>
        </form>
        <button
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setFormError(null);
          }}
          className="mt-4 rounded text-sm text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
        >
          {copy.toggle}
        </button>
      </div>
    </main>
  );
}
