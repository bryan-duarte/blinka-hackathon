from uuid import UUID

from contracts._base import StrictModel


class InvoiceLineItem(StrictModel):
    description: str
    quantity: float
    unit_price: float
    total: float


class InvoiceData(StrictModel):
    vendor: str
    number: str
    issue_date: str | None = None
    due_date: str | None = None
    currency: str
    total_amount: float
    line_items: list[InvoiceLineItem] = []


class InvoiceParseResult(StrictModel):
    file_id: UUID
    invoice: InvoiceData | None = None
    error: str | None = None
