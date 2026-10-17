"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { DecisionCard } from "@/components/bills/DecisionCard";
import { ConsoleShell, ConsoleTopBar } from "@/components/console/ConsoleShell";
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
    <ConsoleShell>
      <ConsoleTopBar
        title="Cola de revisión"
        caption="Facturas de cualquier origen (correo, chat o carga) que esperan una decisión humana."
      />
      <main className="w-full max-w-3xl flex-1 space-y-4 px-4 py-6 md:px-8">
        {loadError && (
          <p role="alert" className="text-sm text-danger">
            <span aria-hidden>✕ </span>
            {loadError}
          </p>
        )}
        {bills === null && !loadError && (
          <div aria-hidden className="h-48 animate-pulse rounded border border-line bg-panel" />
        )}
        {bills?.length === 0 && (
          <p className="rounded border border-line bg-panel p-8 text-sm text-muted">
            No hay facturas esperando una decisión.
          </p>
        )}
        {bills?.map((bill) => (
          <article key={bill.bill_id} className="rounded border border-line bg-panel p-6 md:p-8">
            <DecisionCard
              decision={bill}
              onResolved={loadBills}
              onSelectEmail={() => router.push("/inbox")}
            />
          </article>
        ))}
      </main>
    </ConsoleShell>
  );
}
