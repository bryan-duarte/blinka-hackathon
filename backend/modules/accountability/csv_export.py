import csv
from io import StringIO

from contracts.accountability import LedgerEntryView

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
FORMULA_ESCAPE = "'"
REASON_SEPARATOR = " | "
CSV_COLUMNS = (
    "occurred_at",
    "outcome",
    "actor",
    "payee",
    "payee_kind",
    "category",
    "amount",
    "currency",
    "amount_usd",
    "fx_usd_per_unit",
    "fx_rate_date",
    "fx_source",
    "reasons",
    "explanation",
    "human_note",
    "channel",
    "subject",
    "bill_id",
    "run_id",
)


def write_ledger_csv(entries: list[LedgerEntryView]) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    writer.writerows([_safe_cell(cell) for cell in _csv_row(entry)] for entry in entries)
    return buffer.getvalue()


def _csv_row(entry: LedgerEntryView) -> tuple[object, ...]:
    reasons = REASON_SEPARATOR.join(
        f"{reason.rule_id}: {reason.reason}" for reason in entry.reasons
    )
    return (
        entry.occurred_at.isoformat(),
        entry.outcome,
        entry.actor,
        entry.payee_name,
        entry.payee_kind,
        entry.category,
        entry.amount,
        entry.currency,
        entry.amount_usd,
        entry.fx_usd_per_unit,
        entry.fx_rate_date.isoformat() if entry.fx_rate_date else None,
        entry.fx_source,
        reasons,
        entry.explanation,
        entry.note,
        entry.channel,
        entry.subject,
        entry.bill_id,
        entry.run_id,
    )


def _safe_cell(cell: object) -> str:
    if cell is None:
        return ""
    text = str(cell)
    if text.startswith(FORMULA_PREFIXES):
        return f"{FORMULA_ESCAPE}{text}"
    return text
