from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.accountability import (
    LEDGER_TAB_OUTCOMES,
    CurrencyTotal,
    DecisionLedgerRow,
    InboxLedgerRow,
    LedgerEntryView,
    LedgerFilters,
    LedgerKpis,
    LedgerOutcome,
    LedgerReason,
    LedgerSummaryView,
    LedgerTimelinePoint,
    LimitUsage,
    ReasonCount,
    RunListItemView,
    RunListRow,
)
from contracts.auth import CurrentUser
from contracts.bills import BillStatus
from contracts.inbox import InboxEmailStatus
from contracts.payment_policy import PayeeView
from contracts.payments import BudgetUsageView, DecisionActor, RuleEffect, RunStatus, Verdict
from modules.accountability.csv_export import write_ledger_csv
from modules.accountability.repository import LEDGER_ENTRY_LIMIT, AccountabilityRepository
from modules.payments.budget import CATEGORY_SCOPE_PREFIX, GLOBAL_SCOPE, PAYEE_SCOPE_PREFIX
from modules.payments.errors import RunNotFoundError
from modules.payments.fx import current_period
from modules.payments.rules import RULE_NAMES

if TYPE_CHECKING:
    from clients.payment_policy import PaymentPolicyClient
    from clients.payments import PaymentsClient

TOP_REASON_COUNT = 8
DAYS_PER_WEEK = 7
MONTHS_PER_YEAR = 12
AUTO_PAY_RATE_PRECISION = Decimal("0.0001")
MILLISECONDS_PER_SECOND = 1000
NO_USD = Decimal("0")
DUPLICATE_RULE_ID = "DUP"
GUARD_RULE_ID = "GUARD"
MALWARE_RULE_ID = "MALWARE"
INTAKE_RULE_ID = "INTAKE"
MALWARE_VIOLATION_CODES = frozenset({"attachment.malware", "attachment.scan_failed"})
INTAKE_VIOLATION_CODES = frozenset({"attachment.unreadable"})
GLOBAL_LIMIT_LABEL = "Global"
TERMINAL_RUN_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.FAILED})
STOPPED_USD_OUTCOMES = frozenset(
    {LedgerOutcome.HELD, LedgerOutcome.REJECTED_BY_HUMAN, LedgerOutcome.DUPLICATE}
)
INBOX_OUTCOME_EXPLANATIONS = {
    LedgerOutcome.BLOCKED: "Blocked before reaching the agent.",
    LedgerOutcome.DUPLICATE: "The same message was already received; it was not processed again.",
    LedgerOutcome.NOT_AN_INVOICE: "The agent found nothing to pay in this message.",
    LedgerOutcome.MISSING_INFO: "The agent could not read enough invoice details to pay.",
    LedgerOutcome.ERROR: "Processing failed before a decision was made.",
}
INBOX_STATUS_OUTCOMES = {
    InboxEmailStatus.BLOCKED: LedgerOutcome.BLOCKED,
    InboxEmailStatus.DUPLICATE: LedgerOutcome.DUPLICATE,
    InboxEmailStatus.ERROR: LedgerOutcome.ERROR,
}


class AccountabilityService:
    def __init__(
        self,
        repository: AccountabilityRepository,
        payments: "PaymentsClient",
        policy: "PaymentPolicyClient",
    ) -> None:
        self._repository = repository
        self._payments = payments
        self._policy = policy

    async def ledger_entries(
        self, owner: CurrentUser, filters: LedgerFilters
    ) -> list[LedgerEntryView]:
        entries = await self._entries(owner, filters.period, filters.payee_id, filters.currency)
        if filters.tab == "all":
            return entries
        return _in_tab(entries, filters.tab)

    async def export_csv(self, owner: CurrentUser, filters: LedgerFilters) -> str:
        return write_ledger_csv(await self.ledger_entries(owner, filters))

    async def summary(
        self, owner: CurrentUser, period: str | None, months: int
    ) -> LedgerSummaryView:
        today = datetime.now(UTC).date()
        summary_period = period or current_period(today)
        period_start = _period_start(summary_period)
        window_start = _add_months(period_start, 1 - months)
        window_end = _add_months(period_start, 1)
        window_entries = await self._entries(
            owner,
            None,
            None,
            None,
            since=datetime.combine(window_start, time.min),
            until=datetime.combine(window_end, time.min),
        )
        period_entries = [
            entry for entry in window_entries if f"{entry.occurred_at:%Y-%m}" == summary_period
        ]
        budget_usages = await self._payments.budget_usage(owner, summary_period)
        payees = await self._policy.list_payees(owner)
        return LedgerSummaryView(
            period=summary_period,
            kpis=_kpis(period_entries),
            timeline=_timeline(
                window_entries, window_start, min(today, window_end - timedelta(days=1))
            ),
            limits=_limits(budget_usages, payees),
            top_reasons=_top_reasons(window_entries),
            currencies=_currency_totals(period_entries),
        )

    async def list_runs(
        self, owner: CurrentUser, status: RunStatus | None, limit: int
    ) -> list[RunListItemView]:
        rows = await self._repository.list_runs(owner.user_id, status, limit)
        return [_to_run_view(row) for row in rows]

    async def get_run(self, owner: CurrentUser, run_id: UUID) -> RunListItemView:
        rows = await self._repository.list_runs(owner.user_id, None, 1, run_id)
        if not rows:
            raise RunNotFoundError
        return _to_run_view(rows[0])

    async def _entries(
        self,
        owner: CurrentUser,
        period: str | None,
        payee_id: UUID | None,
        currency: str | None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[LedgerEntryView]:
        decision_rows = await self._repository.decision_rows(
            owner.user_id, period, payee_id, currency, since, until
        )
        entries = [_decision_entry(row) for row in decision_rows]
        is_scoped_to_bills = payee_id is not None or currency is not None
        if not is_scoped_to_bills:
            inbox_rows = await self._repository.inbox_rows(owner.user_id, period, since, until)
            entries.extend(_inbox_entry(row) for row in inbox_rows)
        entries.sort(key=lambda entry: entry.occurred_at, reverse=True)
        return entries[:LEDGER_ENTRY_LIMIT]


def to_decision_outcome(row: DecisionLedgerRow) -> LedgerOutcome:
    if row.actor is DecisionActor.HUMAN:
        if row.verdict is Verdict.PAY:
            return LedgerOutcome.APPROVED_BY_HUMAN
        is_rejected_bill = row.bill_status is BillStatus.REJECTED
        return LedgerOutcome.REJECTED_BY_HUMAN if is_rejected_bill else LedgerOutcome.HELD
    if row.verdict is Verdict.PAY:
        return LedgerOutcome.PAID
    if row.verdict is Verdict.REVIEW:
        return LedgerOutcome.ESCALATED
    is_exact_duplicate = row.duplicate_of_bill_id is not None and any(
        rule_result.get("rule_id") == DUPLICATE_RULE_ID for rule_result in row.rule_results
    )
    return LedgerOutcome.DUPLICATE if is_exact_duplicate else LedgerOutcome.HELD


def to_inbox_outcome(row: InboxLedgerRow) -> LedgerOutcome:
    status_outcome = INBOX_STATUS_OUTCOMES.get(row.status)
    if status_outcome is not None:
        return status_outcome
    if row.run_status is RunStatus.FAILED:
        return LedgerOutcome.ERROR
    if row.has_extraction_failed:
        return LedgerOutcome.MISSING_INFO
    return LedgerOutcome.NOT_AN_INVOICE


def _decision_entry(row: DecisionLedgerRow) -> LedgerEntryView:
    reasons = [
        LedgerReason(
            rule_id=rule_result["rule_id"],
            name=rule_result.get("name", rule_result["rule_id"]),
            effect=RuleEffect(rule_result["effect"]),
            reason=rule_result.get("reason", ""),
        )
        for rule_result in row.rule_results
        if rule_result.get("effect") != RuleEffect.PASS
    ]
    return LedgerEntryView(
        entry_id=row.decision_id,
        occurred_at=row.decided_at,
        outcome=to_decision_outcome(row),
        actor=row.actor,
        payee_id=row.payee_id,
        payee_name=row.payee_name,
        payee_kind=row.payee_kind,
        category=row.category,
        amount=row.amount,
        currency=row.currency,
        amount_usd=row.amount_usd,
        fx_usd_per_unit=row.fx_usd_per_unit,
        fx_rate_date=row.fx_rate_date,
        fx_source=row.fx_source,
        reasons=reasons,
        explanation=row.explanation,
        note=row.note,
        channel=row.source_type,
        subject=row.subject,
        bill_id=row.bill_id,
        run_id=row.run_id,
        inbox_email_id=row.inbox_email_id,
        is_seeded=row.source_type is None,
    )


def _inbox_entry(row: InboxLedgerRow) -> LedgerEntryView:
    outcome = to_inbox_outcome(row)
    reasons = [
        LedgerReason(
            rule_id=_violation_rule_id(violation.get("code", "")),
            name=violation.get("code", ""),
            effect=RuleEffect.HOLD,
            reason=violation.get("message", ""),
        )
        for violation in row.violations
    ]
    explanation = INBOX_OUTCOME_EXPLANATIONS[outcome]
    if outcome is LedgerOutcome.ERROR and row.error:
        explanation = f"{explanation} {row.error}."
    return LedgerEntryView(
        entry_id=row.inbox_email_id,
        occurred_at=row.occurred_at,
        outcome=outcome,
        actor=DecisionActor.AGENT,
        payee_id=None,
        payee_name=None,
        payee_kind=None,
        category=None,
        amount=None,
        currency=None,
        amount_usd=None,
        fx_usd_per_unit=None,
        fx_rate_date=None,
        fx_source=None,
        reasons=reasons,
        explanation=explanation,
        note=None,
        channel=row.source_type,
        subject=row.subject,
        bill_id=None,
        run_id=row.run_id,
        inbox_email_id=row.inbox_email_id,
        is_seeded=False,
    )


def _violation_rule_id(code: str) -> str:
    if code in MALWARE_VIOLATION_CODES:
        return MALWARE_RULE_ID
    if code in INTAKE_VIOLATION_CODES:
        return INTAKE_RULE_ID
    return GUARD_RULE_ID


def _kpis(entries: list[LedgerEntryView]) -> LedgerKpis:
    paid = _in_tab(entries, "paid")
    escalated = _in_tab(entries, "escalated")
    stopped = _in_tab(entries, "stopped")
    agent_bill_decisions = [
        entry for entry in entries if entry.actor is DecisionActor.AGENT and entry.bill_id
    ]
    agent_paid_count = sum(
        1 for entry in agent_bill_decisions if entry.outcome is LedgerOutcome.PAID
    )
    auto_pay_rate = (
        Decimal(agent_paid_count) / Decimal(len(agent_bill_decisions))
        if agent_bill_decisions
        else NO_USD
    )
    return LedgerKpis(
        paid_count=len(paid),
        paid_usd=_usd_total(paid),
        escalated_count=len(escalated),
        escalated_usd=_usd_total(escalated),
        stopped_count=len(stopped),
        stopped_usd=_usd_total(
            [entry for entry in stopped if entry.outcome in STOPPED_USD_OUTCOMES]
        ),
        auto_pay_rate=auto_pay_rate.quantize(AUTO_PAY_RATE_PRECISION),
    )


def _timeline(
    entries: list[LedgerEntryView], window_start: date, window_end: date
) -> list[LedgerTimelinePoint]:
    tab_counts_by_week: dict[date, Counter[str]] = defaultdict(Counter)
    for entry in entries:
        tab_counts_by_week[_week_start(entry.occurred_at.date())][_tab_of(entry.outcome)] += 1
    points = []
    week_start = _week_start(window_start)
    while week_start <= window_end:
        tab_counts = tab_counts_by_week.get(week_start, Counter())
        points.append(
            LedgerTimelinePoint(
                bucket=week_start,
                paid=tab_counts["paid"],
                escalated=tab_counts["escalated"],
                stopped=tab_counts["stopped"],
            )
        )
        week_start += timedelta(days=DAYS_PER_WEEK)
    return points


def _limits(budget_usages: list[BudgetUsageView], payees: list[PayeeView]) -> list[LimitUsage]:
    payees_by_scope = {f"{PAYEE_SCOPE_PREFIX}{payee.payee_id}": payee for payee in payees}
    payee_limits, category_limits, global_limits = [], [], []
    for scope_usage in budget_usages:
        scope = scope_usage.scope
        payee = payees_by_scope.get(scope)
        limit_usage = LimitUsage(
            scope=scope,
            label=_scope_label(scope, payee),
            payee_currency=payee.currency if payee else None,
            spent_usd=scope_usage.reserved_usd,
            limit_usd=scope_usage.limit_usd,
        )
        if scope.startswith(PAYEE_SCOPE_PREFIX):
            payee_limits.append(limit_usage)
        elif scope.startswith(CATEGORY_SCOPE_PREFIX):
            category_limits.append(limit_usage)
        else:
            global_limits.append(limit_usage)
    payee_limits.sort(key=_usage_ratio, reverse=True)
    category_limits.sort(key=_usage_ratio, reverse=True)
    return [*payee_limits, *category_limits, *global_limits]


def _scope_label(scope: str, payee: PayeeView | None) -> str:
    if payee is not None:
        return payee.display_name
    if scope.startswith(CATEGORY_SCOPE_PREFIX):
        return scope.removeprefix(CATEGORY_SCOPE_PREFIX).replace("_", " ").capitalize()
    if scope == GLOBAL_SCOPE:
        return GLOBAL_LIMIT_LABEL
    return scope


def _usage_ratio(limit_usage: LimitUsage) -> Decimal:
    if not limit_usage.limit_usd:
        return NO_USD
    return limit_usage.spent_usd / limit_usage.limit_usd


def _top_reasons(entries: list[LedgerEntryView]) -> list[ReasonCount]:
    reason_counts = Counter(reason.rule_id for entry in entries for reason in entry.reasons)
    names_by_rule = {reason.rule_id: reason.name for entry in entries for reason in entry.reasons}
    return [
        ReasonCount(
            rule_id=rule_id, name=RULE_NAMES.get(rule_id, names_by_rule[rule_id]), count=count
        )
        for rule_id, count in reason_counts.most_common(TOP_REASON_COUNT)
    ]


def _currency_totals(entries: list[LedgerEntryView]) -> list[CurrencyTotal]:
    paid_by_currency: dict[str, list[LedgerEntryView]] = defaultdict(list)
    for entry in _in_tab(entries, "paid"):
        if entry.currency is not None and entry.amount is not None:
            paid_by_currency[entry.currency].append(entry)
    totals = [
        CurrencyTotal(
            currency=currency,
            amount=sum((entry.amount or NO_USD for entry in paid_entries), NO_USD),
            amount_usd=_usd_total(paid_entries),
            count=len(paid_entries),
        )
        for currency, paid_entries in paid_by_currency.items()
    ]
    return sorted(totals, key=lambda currency_total: currency_total.amount_usd, reverse=True)


def _to_run_view(row: RunListRow) -> RunListItemView:
    is_terminal = row.status in TERMINAL_RUN_STATUSES
    duration_ms = (
        round((row.updated_at - row.created_at).total_seconds() * MILLISECONDS_PER_SECOND)
        if is_terminal
        else None
    )
    return RunListItemView(
        run_id=row.run_id,
        status=row.status,
        created_at=row.created_at,
        duration_ms=duration_ms,
        channel=row.source_type,
        sender=row.sender,
        subject=row.subject,
        verdict=row.verdict,
        bill_id=row.bill_id,
        inbox_email_id=row.inbox_email_id,
        tool_count=row.tool_count,
        error=row.error,
    )


def _in_tab(entries: list[LedgerEntryView], tab: str) -> list[LedgerEntryView]:
    tab_outcomes = LEDGER_TAB_OUTCOMES[tab]
    return [entry for entry in entries if entry.outcome in tab_outcomes]


def _tab_of(outcome: LedgerOutcome) -> str:
    return next(tab for tab, outcomes in LEDGER_TAB_OUTCOMES.items() if outcome in outcomes)


def _usd_total(entries: list[LedgerEntryView]) -> Decimal:
    return sum((entry.amount_usd or NO_USD for entry in entries), NO_USD)


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _period_start(period: str) -> date:
    year, month = period.split("-")
    return date(int(year), int(month), 1)


def _add_months(first_day: date, months: int) -> date:
    month_index = first_day.year * MONTHS_PER_YEAR + first_day.month - 1 + months
    return date(month_index // MONTHS_PER_YEAR, month_index % MONTHS_PER_YEAR + 1, 1)
