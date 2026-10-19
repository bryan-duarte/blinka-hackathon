"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { CheckerOpinion, DecisionHistory, EvidenceTable, isCheckerRule } from "@/components/bills/DecisionCard";
import { ReviewActions } from "@/components/bills/ReviewActions";
import { RuleComparison } from "@/components/bills/RuleComparison";
import { ConsoleShell, ConsoleTopBar } from "@/components/console/ConsoleShell";
import { EvidenceSection } from "@/components/files/EvidenceSection";
import { EYEBROW_CLASS, SECONDARY_BUTTON_CLASS } from "@/components/settings/styles";
import { UnauthorizedError, api, tokenStore } from "@/lib/api";
import { formatMoney, formatRelative, formatShortDate, isForeignCurrency } from "@/lib/format";
import { CATEGORY_LABELS, SOURCE_LABELS } from "@/lib/labels";
import { maskEmailsIn } from "@/lib/mask";
import { TERMINAL_RUN_STEPS } from "@/lib/runEvents";
import type { BillDecisionView, BillDetail } from "@/lib/types";
import { useInboxChannel } from "@/lib/useInboxChannel";

const BILL_PARAM = "bill";
const PAGE_CAPTION = "Invoices the agent stopped and sent to a person.";

export default function ReviewQueuePage() {
  return (
    <ConsoleShell>
      <Suspense fallback={<ConsoleTopBar title="Approvals" caption={PAGE_CAPTION} />}>
        <ApprovalsContent />
      </Suspense>
    </ConsoleShell>
  );
}

function ApprovalsContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [bills, setBills] = useState<BillDecisionView[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const requestedBillId = searchParams.get(BILL_PARAM);
  const selectedBill = bills?.find((bill) => bill.bill_id === requestedBillId) ?? bills?.[0] ?? null;
  const totalUsd = (bills ?? []).reduce((sum, bill) => sum + Number(bill.amount_usd ?? 0), 0);
  const caption = bills
    ? `${bills.length} waiting${bills.length > 0 ? ` · USD ${formatMoney(totalUsd, null)}` : ""}`
    : PAGE_CAPTION;

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
        setLoadError("The review queue could not be loaded.");
      });
  }, [router]);

  useInboxChannel((event) => {
    const isTerminalStep = event.type === "run.step" && TERMINAL_RUN_STEPS.has(event.step);
    if (isTerminalStep) loadBills();
  });

  useEffect(() => {
    if (!tokenStore.get()) {
      router.replace("/login");
      return;
    }
    loadBills();
  }, [router, loadBills]);

  function selectBill(billId: string) {
    router.replace(`${pathname}?${BILL_PARAM}=${billId}`, { scroll: false });
  }

  return (
    <>
      <ConsoleTopBar title="Approvals" caption={caption} />
      {loadError && (
        <p role="alert" className="border-b border-line px-4 py-2 text-sm text-danger md:px-8">
          <span aria-hidden>✕ </span>
          {loadError}
        </p>
      )}
      {bills && bills.length > 0 && (
        <nav aria-label="Waiting for you" className="flex gap-2 overflow-x-auto border-b border-line px-4 py-3 md:px-8">
          {bills.map((bill) => {
            const isSelected = bill.bill_id === selectedBill?.bill_id;
            return (
              <button
                key={bill.bill_id}
                type="button"
                aria-current={isSelected}
                onClick={() => selectBill(bill.bill_id)}
                className={`inline-flex h-10 shrink-0 animate-enter items-center gap-2 rounded-full border px-4 text-[13px] whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${isSelected ? "border-ink bg-ink text-white" : "border-selection bg-panel text-ink hover:border-ink"}`}
              >
                <span className="font-medium">{bill.payee_name ?? "Unknown payee"}</span>
                {bill.amount !== null && (
                  <span className={`tabular-nums ${isSelected ? "text-white/70" : "text-muted"}`}>
                    {formatMoney(bill.amount, bill.currency)}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      )}
      {bills === null && !loadError && <ApprovalSkeleton />}
      {bills?.length === 0 && (
        <div className="flex flex-col items-start gap-3 px-4 py-12 md:px-8">
          <p className="font-serif text-[26px] leading-[1.13]">Nothing is waiting for you</p>
          <p className="max-w-[60ch] text-sm text-muted">
            When the agent escalates an invoice, it shows up here with the reason and the files it read.
          </p>
          <Link href="/inbox" className={SECONDARY_BUTTON_CLASS}>
            Go to the inbox
          </Link>
        </div>
      )}
      {selectedBill && <ApprovalDetail key={selectedBill.bill_id} bill={selectedBill} onResolved={loadBills} />}
    </>
  );
}

function ApprovalDetail({ bill, onResolved }: { bill: BillDecisionView; onResolved: () => void }) {
  const [detail, setDetail] = useState<BillDetail | null>(null);
  const [detailError, setDetailError] = useState(false);
  const policyRules = bill.rule_results.filter((rule) => !isCheckerRule(rule));
  const checkerRules = bill.rule_results.filter(isCheckerRule);
  const firstSource = detail?.sources[0];
  const receivedAt = firstSource?.received_at ?? firstSource?.created_at ?? bill.decided_at;
  const eyebrowParts = [
    bill.category ? CATEGORY_LABELS[bill.category] : null,
    firstSource ? SOURCE_LABELS[firstSource.source_type] : null,
    formatRelative(receivedAt),
  ].filter(Boolean);
  const amountLabel = bill.amount !== null ? formatMoney(bill.amount, bill.currency) : null;
  const dueDate = bill.candidate?.due_date ?? null;

  useEffect(() => {
    let isActive = true;
    api
      .bill(bill.bill_id)
      .then((billDetail) => isActive && setDetail(billDetail))
      .catch(() => isActive && setDetailError(true));
    return () => {
      isActive = false;
    };
  }, [bill.bill_id]);

  return (
    <main className="flex flex-wrap items-start gap-8 px-4 py-8 md:px-8">
      <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-8">
        <header className="flex flex-col gap-2">
          <p className={EYEBROW_CLASS}>{eyebrowParts.join(" · ")}</p>
          <h2 className="font-serif text-[38px] leading-[1.15] text-ink">{bill.payee_name ?? "Unknown payee"}</h2>
          <p className="max-w-[68ch] text-base leading-[1.5] text-muted">{bill.explanation}</p>
          {firstSource?.sender && (
            <p className="text-[13px] text-muted">From {maskEmailsIn(firstSource.sender)}</p>
          )}
        </header>
        <RuleComparison rules={policyRules} />
        {detailError && <p className="text-sm text-muted">The invoice files could not be loaded.</p>}
        {detail === null && !detailError && <div aria-hidden className="h-24 animate-pulse rounded-lg bg-sunken" />}
        {detail && <EvidenceSection evidence={detail.evidence} />}
        {bill.candidate && <EvidenceTable candidate={bill.candidate} />}
        {checkerRules.length > 0 && <CheckerOpinion rules={checkerRules} />}
        <DecisionHistory billId={bill.bill_id} />
      </div>
      <aside
        aria-label="Your decision"
        className="flex flex-[1_1_320px] flex-col gap-5 rounded-lg border border-ink bg-panel p-6 lg:sticky lg:top-6"
      >
        <div className="flex flex-col gap-1">
          <p className="font-serif text-[38px] leading-[1.15] tabular-nums">{amountLabel ?? "No amount"}</p>
          <p className="text-sm text-muted tabular-nums">
            {[
              bill.amount_usd !== null && isForeignCurrency(bill.currency)
                ? `≈ USD ${formatMoney(bill.amount_usd, null)}`
                : null,
              dueDate ? `due ${formatShortDate(dueDate)}` : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        {bill.can_approve ? (
          <ReviewActions
            billId={bill.bill_id}
            approveLabel={amountLabel ? `Approve ${amountLabel}` : "Approve payment"}
            onResolved={onResolved}
          />
        ) : (
          <p className="text-sm text-muted">You can view this invoice but not approve it.</p>
        )}
      </aside>
    </main>
  );
}

function ApprovalSkeleton() {
  return (
    <div aria-hidden className="flex flex-wrap gap-8 px-4 py-8 md:px-8">
      <div className="flex flex-[999_1_560px] flex-col gap-4">
        <div className="h-3.5 w-1/4 animate-pulse rounded bg-sunken" />
        <div className="h-10 w-1/2 animate-pulse rounded bg-sunken" />
        <div className="h-48 animate-pulse rounded-lg bg-sunken" />
      </div>
      <div className="h-80 flex-[1_1_320px] animate-pulse rounded-lg bg-sunken" />
    </div>
  );
}
