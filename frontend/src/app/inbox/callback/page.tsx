"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { UnauthorizedError, api } from "@/lib/api";
import type { MailAccountStatus } from "@/lib/types";

const CONFIRM_ATTEMPTS = 10;
const CONFIRM_RETRY_DELAY_MS = 1000;
const SUCCESS_STATUS = "success";

type CallbackState =
  | { phase: "confirming" }
  | { phase: "failed"; message: string };

const FINAL_STATUS_MESSAGES: Record<Exclude<MailAccountStatus, "active">, string> = {
  initiated: "La conexión sigue pendiente. Intenta de nuevo en unos segundos.",
  failed: "El proveedor rechazó la conexión.",
  expired: "La conexión expiró. Vuelve a conectar el correo.",
};

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function confirmUntilSettled(connectedAccountId: string): Promise<MailAccountStatus> {
  let status: MailAccountStatus = "initiated";
  for (let attempt = 0; attempt < CONFIRM_ATTEMPTS && status === "initiated"; attempt += 1) {
    if (attempt > 0) await wait(CONFIRM_RETRY_DELAY_MS);
    status = (await api.confirm(connectedAccountId)).status;
  }
  return status;
}

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const connectedAccountId = searchParams.get("connected_account_id");
  const isProviderSuccess = searchParams.get("status") === SUCCESS_STATUS;
  const [state, setState] = useState<CallbackState>({ phase: "confirming" });

  useEffect(() => {
    if (!isProviderSuccess || !connectedAccountId) return;
    let isCancelled = false;
    confirmUntilSettled(connectedAccountId)
      .then((status) => {
        if (isCancelled) return;
        if (status === "active") {
          router.replace("/inbox");
          return;
        }
        setState({ phase: "failed", message: FINAL_STATUS_MESSAGES[status] });
      })
      .catch((error: unknown) => {
        if (isCancelled) return;
        if (error instanceof UnauthorizedError) {
          router.replace("/login");
          return;
        }
        setState({ phase: "failed", message: "No se pudo confirmar la conexión." });
      });
    return () => {
      isCancelled = true;
    };
  }, [connectedAccountId, isProviderSuccess, router]);

  const failureMessage =
    !isProviderSuccess || !connectedAccountId
      ? "El proveedor no completó la autorización."
      : state.phase === "failed"
        ? state.message
        : null;

  if (failureMessage) {
    return (
      <div role="alert" className="space-y-3">
        <p className="text-sm text-danger">{failureMessage}</p>
        <Link href="/inbox" className="text-sm font-medium text-accent hover:underline">
          Volver a la bandeja
        </Link>
      </div>
    );
  }
  return <CallbackSpinner />;
}

function CallbackSpinner() {
  return (
    <p aria-live="polite" className="flex items-center gap-3 text-sm text-muted">
      <span
        aria-hidden
        className="size-4 animate-spin rounded-full border-2 border-line border-t-accent"
      />
      Confirmando la conexión con tu correo...
    </p>
  );
}

export default function MailboxCallbackPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-lg border border-line bg-panel p-6">
        <Suspense fallback={<CallbackSpinner />}>
          <CallbackContent />
        </Suspense>
      </div>
    </main>
  );
}
