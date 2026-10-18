"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { UnauthorizedError, api } from "@/lib/api";

const COMPLETED_STATUS = "completed";
const UNKNOWN_FAILURE_MESSAGE = "No se pudo conectar WhatsApp";
const SETUP_ERROR_MESSAGES: Record<string, string> = {
  facebook_auth_failed: "No se pudo autenticar con Meta",
  phone_verification_failed: "No se pudo verificar el número",
  link_expired: "El enlace expiró, vuelve a intentarlo",
  already_used: "Este enlace ya se usó",
};

function setupFailureMessage(errorCode: string | null): string {
  return (errorCode && SETUP_ERROR_MESSAGES[errorCode]) || UNKNOWN_FAILURE_MESSAGE;
}

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const setupLinkId = searchParams.get("setup_link_id");
  const phoneNumberId = searchParams.get("phone_number_id");
  const errorCode = searchParams.get("error_code");
  const isSetupCompleted =
    searchParams.get("status") === COMPLETED_STATUS && Boolean(setupLinkId && phoneNumberId);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const hasRequestedConfirm = useRef(false);

  useEffect(() => {
    if (!isSetupCompleted || !setupLinkId || !phoneNumberId || hasRequestedConfirm.current) return;
    hasRequestedConfirm.current = true;
    api
      .confirmWhatsApp(setupLinkId, phoneNumberId)
      .then(() => router.replace("/inbox"))
      .catch((error: unknown) => {
        if (error instanceof UnauthorizedError) {
          router.replace("/login");
          return;
        }
        setConfirmError(UNKNOWN_FAILURE_MESSAGE);
      });
  }, [isSetupCompleted, setupLinkId, phoneNumberId, router]);

  const failureMessage = !isSetupCompleted ? setupFailureMessage(errorCode) : confirmError;

  if (failureMessage) {
    return (
      <div role="alert" className="flex flex-col gap-3">
        <p className="text-sm text-danger">{failureMessage}</p>
        <Link href="/inbox" className="text-sm font-normal text-accent hover:underline">
          Volver a la bandeja
        </Link>
      </div>
    );
  }
  return <CallbackProgress />;
}

function CallbackProgress() {
  return (
    <p aria-live="polite" className="flex items-center gap-3 text-sm text-muted">
      <span
        aria-hidden
        className="size-4 animate-spin rounded-full border-2 border-line border-t-accent"
      />
      Confirmando tu número de WhatsApp…
    </p>
  );
}

export default function WhatsAppCallbackPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-lg border border-line bg-panel p-6">
        <Suspense fallback={<CallbackProgress />}>
          <CallbackContent />
        </Suspense>
      </div>
    </main>
  );
}
