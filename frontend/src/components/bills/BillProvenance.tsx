import { useEffect, useState } from "react";
import { EvidenceSection } from "@/components/files/EvidenceSection";
import { SourceBadge } from "@/components/inbox/SourceBadge";
import { api } from "@/lib/api";
import type { BillDetail } from "@/lib/types";

export function BillProvenance({ billId }: { billId: string }) {
  const [detail, setDetail] = useState<BillDetail | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    let isActive = true;
    api
      .bill(billId)
      .then((billDetail) => isActive && setDetail(billDetail))
      .catch(() => isActive && setLoadError(true));
    return () => {
      isActive = false;
    };
  }, [billId]);

  if (loadError) {
    return <p className="text-xs text-muted">The invoice source could not be loaded.</p>;
  }
  if (detail === null) {
    return <div aria-hidden className="h-3.5 w-24 animate-pulse rounded bg-sunken" />;
  }
  const firstSource = detail.sources[0];
  return (
    <div className="space-y-4">
      {firstSource && <SourceBadge type={firstSource.source_type} showsLabel />}
      <EvidenceSection evidence={detail.evidence} />
    </div>
  );
}
