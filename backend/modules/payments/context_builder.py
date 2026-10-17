from datetime import UTC, datetime, time, timedelta

from pydantic import TypeAdapter

from contracts.bills import BillRecord, BillSourceRecord
from contracts.payment_candidates import (
    BillClassification,
    PaymentCandidate,
    PaymentCandidateBase,
)
from contracts.payment_policy import PayeeMatch, PaymentPolicy
from modules.payments.budget import budget_charges
from modules.payments.dependencies import PaymentRunDependencies
from modules.payments.fx import current_period, to_usd
from modules.payments.rules import DecisionContext

PAYMENT_CANDIDATE_ADAPTER: TypeAdapter[PaymentCandidateBase] = TypeAdapter(PaymentCandidate)


async def build_context(
    dependencies: PaymentRunDependencies,
    bill: BillRecord,
    source: BillSourceRecord,
    candidate: PaymentCandidateBase,
    match: PayeeMatch,
    policy: PaymentPolicy,
    classification: BillClassification | None = None,
) -> DecisionContext:
    owner_id = bill.owner_id
    today = datetime.now(UTC).date()
    blacklist_hits = await dependencies.policy.find_blacklist_hits(
        owner_id, candidate, source.sender
    )
    recent_bills = []
    if match.payee is not None:
        window_start = datetime.combine(
            today - timedelta(days=policy.duplicate_window_days), time.min
        )
        recent_bills = await dependencies.bills.recent_canonical_bills(
            owner_id, match.payee.payee_id, window_start, bill.bill_id
        )
    scopes = [charge.scope for charge in budget_charges(policy, match.payee, candidate.category)]
    budget = await dependencies.ledger.budget_snapshot(owner_id, current_period(today), scopes)
    return DecisionContext(
        candidate=candidate,
        bill=bill,
        source=source,
        match=match,
        policy=policy,
        blacklist_hits=blacklist_hits,
        amount_usd=to_usd(candidate.amount, candidate.currency),
        recent_bills=recent_bills,
        budget=budget,
        today=today,
        classification=classification,
    )


async def rebuild_context(
    dependencies: PaymentRunDependencies, bill: BillRecord, policy: PaymentPolicy
) -> DecisionContext:
    candidate = PAYMENT_CANDIDATE_ADAPTER.validate_python(bill.candidate)
    sources = await dependencies.bills.list_sources_for_bill(bill.owner_id, bill.bill_id)
    source = sources[0]
    match = await dependencies.policy.match_payee(bill.owner_id, candidate, source.sender)
    return await build_context(dependencies, bill, source, candidate, match, policy)


def parse_candidate(bill: BillRecord) -> PaymentCandidateBase | None:
    if not bill.candidate:
        return None
    return PAYMENT_CANDIDATE_ADAPTER.validate_python(bill.candidate)
