"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { DecisionCard } from "@/components/bills/DecisionCard";
import { UnauthorizedError, api, tokenStore } from "@/lib/api";
import type { BillDecisionView } from "@/lib/types";

export default function ReviewQueuePage() {
  const router = useRouter();
  const [bills, setBills] = useState<BillDecisionView[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadBills = useCallback(() => {
    api
      .bills("review")
      .then((reviewBills) => {
        setBills(reviewBills);
        setLoadError(null);
      })
      .catch((error: unknown) => {
        if (error instanceof UnauthorizedError) {
          router.replace("/login");
          return;
        }
        setLoadError("No se pudo cargar la cola de revisión.");
      });
  }, [router]);

  useEffect(() => {
    if (!tokenStore.get()) {
      router.replace("/login");
      return;
    }
    loadBills();
  }, [router, loadBills]);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-panel">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3 md:px-6">
          <h1 className="text-base font-[450] tracking-[-0.02em] text-ink">Cola de revisión</h1>
          <Link
            href="/inbox"
            className="rounded px-1 text-sm text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
          >
            ← Volver a la bandeja
          </Link>
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 space-y-4 px-4 py-6 md:px-6">
        <p className="text-sm text-muted">
          Facturas de cualquier origen (correo, chat o carga) que esperan una decisión humana.
        </p>
        {loadError && (
          <p role="alert" className="text-sm text-danger">
            {loadError}
          </p>
        )}
        {bills === null && !loadError && (
          <div aria-hidden className="h-48 animate-pulse rounded-md border border-line bg-panel" />
        )}
        {bills?.length === 0 && (
          <p className="rounded-md border border-line bg-panel p-5 text-sm text-muted">
            No hay facturas esperando una decisión.
          </p>
        )}
        {bills?.map((bill) => (
          <DecisionCard
            key={bill.bill_id}
            decision={bill}
            onResolved={loadBills}
            onSelectEmail={() => router.push("/inbox")}
          />
        ))}
      </main>
    </div>
  );
}
