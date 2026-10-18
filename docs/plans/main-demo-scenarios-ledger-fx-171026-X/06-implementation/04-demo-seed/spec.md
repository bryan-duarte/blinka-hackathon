# Demo Seed Implementation

## Overview

This step builds the initial state of the demo account: company policy, payees (persons, companies, services), blacklist, and backdated history covering 3 past months plus the current one. The current month is pre-filled so the limit scenarios fire. A styled PDF renderer for the scenario documents also lives here.

## Files to Modify/Create

- `backend/modules/demo/__init__.py` (new): re-exports `DemoService`, `DemoSeeder`, `DemoSeedRepository`, `DemoResetRepository`, errors, `__all__`.
- `backend/modules/demo/seed_data.py` (new): pure data, no I/O.
  - `DEMO_POLICY: PaymentPolicyUpdate`
  - `DEMO_PAYEES: tuple[PayeeCreate, ...]`
  - `DEMO_BLACKLIST: tuple[BlacklistEntryCreate, ...]`
  - `SEED_USD_PER_UNIT_BY_MONTH: dict[int, dict[str, Decimal]]`, keyed by month offset (0 = current, -1, -2, -3)
  - `HistoricalBill` dataclass
  - `def history(today: date) -> list[HistoricalBill]`
- `backend/modules/demo/seeder.py` (new): `DemoSeeder(policy: PaymentPolicyClient, seed_repository: DemoSeedRepository)` with `async seed(owner: CurrentUser) -> int` (returns the number of seeded bills).
- `backend/modules/demo/seed_repository.py` (new): `DemoSeedRepository(sessionmaker)` with `async insert_history(owner_id, payee_ids_by_name, bills: list[HistoricalBill]) -> int`. It writes `Bill`, `PaymentDecisionRow`, `PaymentRow` and the `BudgetCounterRow` upserts in one transaction.
- `backend/modules/demo/documents.py` (new): the fpdf2 renderer, described below.
- `backend/scripts/seed_demo.py` (new): CLI `uv run python -m scripts.seed_demo [--reset]`. It builds settings, pools and clients the same way `lifespan` does, then calls `clients.demo.ensure_demo_account()`, or `clients.demo.reset(owner)` when `--reset` is passed.
- `backend/scripts/seed_payment_policy.py`: delete it, since `seed_data.py` replaces it. Move any constants still used elsewhere.
- `backend/pyproject.toml`: add `fpdf2` with `uv add fpdf2`, pinned to the resolved exact version.

## Implementation Guidelines

### Company and policy (`seed_data.py`)

The company is Andescape Labs, Inc., a Delaware company whose base currency is USD.

```python
DEMO_POLICY = PaymentPolicyUpdate(
    hard_cap_per_payment_usd=Decimal("8000"),
    auto_pay_max_usd=Decimal("2500"),
    monthly_budget_usd=Decimal("30000"),
    category_monthly_budgets_usd={
        PaymentCategory.CLOUD: Decimal("4000"),
        PaymentCategory.SAAS: Decimal("1500"),
        PaymentCategory.CONTRACTOR: Decimal("9000"),
        PaymentCategory.PROFESSIONAL_SERVICES: Decimal("10000"),
        PaymentCategory.RENT: Decimal("1500"),
        PaymentCategory.UTILITIES: Decimal("500"),
    },
    allowed_categories=[CLOUD, SAAS, CONTRACTOR, PROFESSIONAL_SERVICES, RENT, UTILITIES],  # MARKETING not allowed
    allowed_currencies=["USD", "CLP", "CLF", "MXN", "COP", "BRL", "EUR"],                 # TRY/ARS not allowed
)
```

### Payees (`DEMO_PAYEES`, 11 entries)

All limits are in USD.

| # | display_name | kind | country / currency | category | method | limits / agreement | identifiers |
|---|---|---|---|---|---|---|---|
| 1 | Amazon Web Services | service | US / USD | cloud | card_on_file | — | domain aws.amazon.com, domain amazon.com, service_account_id 123456789012, alias aws |
| 2 | ACME Cloud | service | US / USD | saas | bank_transfer | agreed 120 ±5% | domain acmecloud.io, bank 000123456789 |
| 3 | Nubio Software Ltda | service | BR / BRL | saas | bank_transfer | agreed 95 ±8% | domain nubio.com.br, tax_id 12.345.678/0001-90, email cobranca@nubio.com.br |
| 4 | Servicios Integrales del Sur SpA | company | CL / CLP | professional_services | bank_transfer | per_payment_max 3000 | tax_id 76.543.210-K, bank CL-001-2233445566, email facturacion@sisur.cl |
| 5 | Agencia Brava S.A. de C.V. | company | MX / MXN | professional_services | bank_transfer | agreed 1800 ±6% | tax_id ABR190312KX1, domain agenciabrava.mx, bank 012180001234567891 |
| 6 | Kessler Consulting GmbH | company | DE / EUR | professional_services | bank_transfer | — | tax_id DE811234567, domain kessler-consulting.de, bank DE89370400440532013000 |
| 7 | Inmobiliaria Providencia Ltda | company | CL / CLF | rent | bank_transfer | agreed 1150 ±5% | tax_id 77.888.999-1, email arriendos@iprovidencia.cl, bank CL-BCI-11223344 |
| 8 | María José Pérez | person | CL / USD | contractor | bank_transfer | monthly 1500, agreed 900 ±0% | tax_id 15234567-8, bank CL-BE-99887766, email maria.perez.dev@gmail.com |
| 9 | Andrés Felipe Gómez | person | CO / COP | contractor | bank_transfer | monthly 2000, agreed 2000 ±3% | tax_id 1020456789, bank CO-BANCOLOMBIA-45678901234, email andres.gomez.dev@gmail.com |
| 10 | Lucía Hernández | person | MX / MXN | contractor | bank_transfer | monthly 1400, agreed 1200 ±3% | tax_id HELU920514AB3, bank 002180700112233445, email lucia.hdz.design@gmail.com |
| 11 | Datacorp Chile SpA | service | CL / CLP | utilities | bank_transfer | — | domain datacorp.cl, email facturacion@datacorp.cl, tax_id 96.555.444-3 |

Put the country in `attributes={"country": "CO"}`, the same way the existing payees store attributes. Check how `PayeeRecord.attributes` is used today first.

### Blacklist (`DEMO_BLACKLIST`)

- bank_account `US-CHASE-55554444`: "reported account"
- domain `amaz0n-billing.com`: "phishing domain"
- alias `Proveedor Fantasma`: "non-existent vendor"
- bank_account `CO-NEQUI-3001112233`: "account flagged in fraud report"

### History (`history(today)`)

`HistoricalBill` fields:
- `payee_name`, `invoice_number`, `amount`, `currency`, `category`
- `issued_on`, `due_on`, `decided_at`
- `verdict`, `final_status` (BillStatus), `actor`
- `rule_results: list[RuleResult]`, `explanation`, `note`
- `is_paid`

Per past month (offsets -3, -2, -1), dated on fixed days of that month:

- AWS: USD 3,410 / 3,560 / 3,690, paid, invoice `AWS-{yyyymm}-01`.
- ACME Cloud: USD 120, paid, `INV-19{mm}`.
- Nubio: BRL 520, paid.
- Sisur: CLP 1,100,000–1,350,000, paid.
- Brava: MXN 33,000, paid.
- Providencia: CLF 28, paid.
- María: USD 900, paid.
- Andrés: COP 8,200,000, paid.
- Lucía: MXN 21,500, paid.
- Datacorp: CLP 89,990, paid. Due on day 5 of each month.

Non-pay entries, for chart variety:
- Month -2, Kessler EUR 2,900 (≈ USD 3,130): verdict REVIEW (R13), then a human approval decision (`actor=human`, note "Approved by CFO: quarterly workshop"), status PAID. This needs 2 decision rows.
- Month -1, "Amaz0n Billing" USD 1,250: HOLD (R03 blacklisted), status HELD, no payment, `payee_id=None`.
- Month -1, ACME USD 180: REVIEW (R17), then a human reject ("Not the agreed price"), status REJECTED.
- Month -3, ACME `INV-19{mm}` resent: duplicate HOLD (DUP), status DUPLICATE, `duplicate_of_bill_id` = the original.

Current month (offset 0). Dates are `max(month_start, today - n days)` so the first day of the month still works:

- Andrés COP 8,200,000 (≈ USD 2,000), paid. The payee scope reaches 2000/2000, which drives the `payee_limit_reached` scenario.
- AWS USD 3,540, invoice `AWS-{yyyymm}-01`, paid. The cloud scope reaches 3,540/4,000.
- Sisur CLP 1,150,000, invoice `F-6188`, paid. This is the target of `dup_against_history`. Keep its fingerprint inputs (payee_id, normalized invoice number `F6188` as produced by `normalize_invoice_number`, amount, `CLP`) identical to what the scenario document will extract.
- María, Lucía, ACME, Nubio, Kessler, Brava, Providencia and Datacorp have no entries in the current month, so the happy-path and budget-sequence scenarios start from a clean month.

Convert with `SEED_USD_PER_UNIT_BY_MONTH[offset][currency]`, and set `fx_source=FxSource.SEED` and `fx_rate_date` to the decision date. Keep the rates close to `STATIC_USD_PER_UNIT` so the charts look realistic.

### Writing history (`DemoSeedRepository.insert_history`)

For each `HistoricalBill`, inside one `session.begin()`:

1. Insert a `Bill` row with an explicit `created_at=updated_at=decided_at`.
   - `fingerprint` comes from `bill_fingerprint(owner_id, str(payee_id) or normalized_name, normalize_invoice_number(n), due_on, amount, currency)`. Reuse `modules/bills/hashing.py`, the same inputs `BillsService.claim_bill` uses.
   - `candidate` is built with the matching `ServiceCandidate`, `PersonCandidate` or `CompanyCandidate` and stored with `.model_dump(mode="json")`, with evidence quotes such as `"Total: CLP 1.150.000"`.
   - Duplicates set `duplicate_of_bill_id` and `fingerprint=None` to satisfy the partial unique index.
2. Insert the `PaymentDecisionRow`(s) with `run_id=None`, `policy_id` set to the active policy, and backdated `created_at`.
3. For paid bills, insert a `PaymentRow` with status `executed`, `rail_reference=str(uuid5(PAYMENTS_NAMESPACE, key))`, `period=f"{decided_at:%Y-%m}"`, `scopes` from `budget_charges(policy, payee, category)`, the FX fields and backdated timestamps.
4. Upsert the `BudgetCounterRow` for each scope and period: `insert(...).on_conflict_do_update(index_elements=[owner_id, scope, period], set_={reserved_usd: reserved_usd + excluded})`. Check the counter's real PK column names in `modules/payments/models.py`.

The seeder flow is: `policy.update_policy(owner, DEMO_POLICY)`, then for each payee `policy.create_payee(owner, payee)` (collecting `payee_ids_by_name`), then for each blacklist entry `policy.add_blacklist_entry`, then `seed_repository.insert_history(...)`. Before seeding, `ensure_demo_account` skips when `policy.get_policy` succeeds, i.e. the account is already seeded.

### Styled documents (`documents.py`)

```python
@dataclass(frozen=True)
class InvoiceLine:
    description: str
    quantity: Decimal
    unit_price: Decimal

@dataclass(frozen=True)
class InvoiceDocument:
    language: Literal["es", "pt", "en"]
    issuer_name: str
    issuer_tax_id: str | None
    issuer_address: str
    issuer_email: str | None
    bill_to: str                    # "Andescape Labs, Inc. · 251 Little Falls Dr, Wilmington, DE"
    title: str                      # "FACTURA", "CUENTA DE COBRO", "INVOICE", "NOTA FISCAL DE SERVIÇO"
    number: str
    issued_on: date
    due_on: date | None
    currency: str
    currency_label: str             # explicit marker, e.g. "COP", "US$", "R$", "UF" (keeps R01/R09 explicit-currency checks passing)
    lines: list[InvoiceLine]
    tax_label: str | None           # "IVA 19%", "IVA 16%", "USt. 19%"
    tax_rate: Decimal | None
    payment_details: list[str]      # bank / account / CLABE / IBAN lines
    notes: list[str] = field(default_factory=list)
    hidden_text: str | None = None  # injection-in-PDF scenario: white 4pt text

def render_invoice_pdf(document: InvoiceDocument) -> bytes: ...
def render_scanned_invoice_pdf(document: InvoiceDocument) -> bytes:
    """Rasterize the invoice with Pillow (ImageDraw on a 1240x1754 white canvas, slight rotation/noise)
    and embed only the image, so the PDF has no text layer and Textract must OCR it."""
def render_xml_cfdi(...) -> bytes  # CFDI 4.0 Comprobante for Agencia Brava (MXN)
def render_xml_dte(...) -> bytes   # move SISUR_DTE_XML template from samples.py, parametrized by folio/amount
```

- The layout uses fpdf2 core Helvetica (latin-1 covers á é í ó ú ñ ã ç). It has the issuer block top-left, the title and number top-right, a hairline rule, the bill-to block, the line-item table (Description / Qty / Unit / Amount), subtotal, tax and total (`{currency_label} {total}`), the payment-details block and a footer note. Use one accent color only (cobalt `#2a4bd0`) for the title, to stay on brand.
- Number formatting follows the document language: `es` CL/CO use `1.150.000`, MX uses `33,000.00`, and `en` uses `3,540.00`. Totals must be arithmetically correct, because R-rules and the checker compare them.
- Check that the XML templates parse with `modules/invoice_ingestor/xml_parser.parse_invoice_xml` and are detected as `cfdi_mx` / `dte_cl`. Reuse the shapes in `tests/fixtures/xml/` as the reference.

## Dependencies

- 01 (`DemoSettings`), 02 (FX columns, `FxSource.SEED`) and 03 (English rule reasons for the seeded `rule_results`).
- `fpdf2` (new) and Pillow (transitive).

## Integration Notes

- 05-demo-scenarios builds every attachment through `render_invoice_pdf`, `render_scanned_invoice_pdf`, `render_xml_cfdi` and `render_xml_dte`.
- 06-demo-reset calls `DemoSeeder.seed(owner)` after the purge.
- `HistoricalBill.rule_results` must include the full rule list (pass results too) so `DecisionCard` renders it like a live decision. Build it with the English names from 03.

### Scenario isolation invariant

The scenarios in 05 are designed so that, after a reset, each one can run once, in any order, and still produce its expected outcome:
- Every PAY scenario uses a different payee or a clearly different amount, so R11 (±0.5% amount within a 10-day due-date window) never links two scenarios by accident.
- The seeded current-month totals leave room for every PAY scenario together: professional_services stays under 10,000, cloud stays under 4,000 until the category sequence, and global stays under 30,000.

If you change any amount here or in 05, recompute these totals.
