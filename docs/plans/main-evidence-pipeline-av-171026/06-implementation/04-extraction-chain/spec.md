# Extraction Chain — deterministic multi-country XML → LLM → Textract → no_info

## Overview

Rework extraction in `invoice_ingestor` around the primary/secondary file roles: deterministic multi-country XML parsing (format registry: CFDI MX, DTE CL, UBL CO/PE/EU, CII EU) with LLM fallback, existing PDF-text LLM path, and Textract `AnalyzeExpense` as the visual last resort, ending in an explicit `no_info` terminal state instead of a failed run.

## Files to Modify/Create

- `backend/modules/files/extract.py` — `extract_preview`: add `application/xml` branch (currently only `text/*` passes); XML decodes with a charset fallback, capped at `MAX_EXTRACT_CHARS`
- `backend/modules/invoice_ingestor/xml_parser.py` (new) — format registry: `detect_format(root) -> XmlInvoiceFormat`, `parse_invoice_xml(text: str) -> ParsedXmlInvoice | None`, one mapper function per format
- `backend/tests/fixtures/xml/` (new) — minimal fixtures: `cfdi_mx.xml`, `dte_cl.xml`, `ubl_co.xml`, `ubl_pe.xml`, `ubl_eu.xml`, `unknown.xml`
- `backend/tests/test_xml_parser.py` (new) — deterministic detection + mapping tests per fixture (no LLM)
- `backend/modules/textract_gateway/` (new) — `service.py` (`TextractGatewayService.analyze_expense`), `errors.py`, thin client `backend/clients/textract.py`, wiring in `backend/container.py`
- `backend/modules/invoice_ingestor/service.py` — `extract_candidate` becomes the chain; `_build_user_content` gains the XML-as-text path for the LLM fallback
- `backend/modules/payments/runner.py` — catch extraction failure → `EXTRACTION_FAILED_STEP` event → complete run without decision; constant added to the step block (:25-34)
- `backend/modules/inbox/service.py` — `_resolve_status` (:171-186): completed + no bill + last event `extraction_failed` → `InboxEmailStatus.NO_INFO`
- `backend/contracts/inbox.py` — `InboxEmailStatus.NO_INFO = "no_info"`
- `backend/pyproject.toml` — add `defusedxml`

## Implementation Guidelines

Format registry (deterministic; confidence 1.0, evidence = raw attribute values). Detection is by root tag namespace — every supported format is uniquely identifiable this way, and each carries explicit country + ISO-4217 currency fields:

```python
class XmlInvoiceFormat(StrEnum):
    CFDI_MX = "cfdi_mx"   # Mexico
    DTE_CL  = "dte_cl"    # Chile (SII)
    UBL     = "ubl"       # Colombia (DIAN), Peru (SUNAT), EU (Peppol) — country read per-document
    CII     = "cii"       # EU ZUGFeRD / Factur-X / XRechnung-CII
    UNKNOWN = "unknown"

def detect_format(root) -> XmlInvoiceFormat:
    ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
    local = root.tag.rsplit("}", 1)[-1]
    if ns.startswith("http://www.sat.gob.mx/cfdi/") and local == "Comprobante": return CFDI_MX
    if ns == "http://www.sii.cl/SiiDte" and local in {"DTE", "Documento"}:      return DTE_CL
    if ns == "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" and local == "Invoice": return UBL
    if ns.startswith("urn:un:unece:uncefact:data:standard:CrossIndustryInvoice"): return CII
    return UNKNOWN
```

Per-format field mapping (each mapper returns `ParsedXmlInvoice{candidate: PaymentCandidate, format, country, currency}`):

| Field | CFDI (MX) | DTE (CL) | UBL (CO/PE/EU) | CII (EU) |
|---|---|---|---|---|
| payee_name / legal_name | `Emisor@Nombre` | `Encabezado/Emisor/RznSoc` | `cac:AccountingSupplierParty//cbc:RegistrationName` | `ram:SellerTradeParty/ram:Name` |
| tax_id | `Emisor@Rfc` | `Emisor/RUTEmisor` | `//cbc:CompanyID` | `ram:SellerSpecifiedLegalOrganization/ram:ID` |
| amount | `@Total` | `Totales/MntTotal` | `cac:LegalMonetaryTotal/cbc:PayableAmount` | `ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:GrandTotalAmount` |
| currency | `@Moneda` (ISO 4217) | `Totales/TpoMoneda`, **default `CLP` when absent** | `cbc:DocumentCurrencyCode` or `@currencyID` on the amount | `@currencyID` on the amount / `ram:InvoiceCurrencyCode` |
| country | `MX` implied | `CL` implied | supplier `cac:PostalAddress/cac:Country/cbc:IdentificationCode` (ISO 3166; CO/PE/DE/…) — secondary hint: `cbc:CustomizationID`/`cbc:ProfileID` (DIAN/SUNAT URNs) | seller `ram:PostalTradeAddress/ram:CountryID` |
| invoice_number | `@Serie`+`@Folio` (or `tfd:TimbreFiscalDigital@UUID`) | `Documento@Folio` (prefixed by `@tipoDTE` 33/34/43) | `cbc:ID` (CUFE in `cbc:UUID`) | `ram:ApplicableHeaderTradeDelivery`… use `ram:SpecifiedTradeProduct`→ header `ram:ID` / `cbc:ID` equivalent (`ram:ExchangedDocument/ram:ID`) |
| issue_date | `@Fecha` | `Documento@FdtEmision`/`Encabezado/IdDoc/FchEmis` | `cbc:IssueDate` | `ram:IssueDateTime/udt:DateTimeString` |

DTE specifics: only treat `@tipoDTE` ∈ {33, 34, 43, 46} as bills (factura electrónica / exenta / liquidación); others (61 boleta, 52 guía…) → return `None` (classification path decides). Amounts: DTE `MntTotal` may carry `MntExe` for exentas — use `Totales/MntTotal + MntExe` if present (keep it simple: `MntTotal`, note the limitation). UBL: filter to invoice-ish `cbc:InvoiceTypeCode` when present; DIAN uses codes like `01`/`03`, SUNAT `01` with series prefix in `cbc:ID` (e.g. `F001-123`).

```python
def parse_invoice_xml(text: str) -> ParsedXmlInvoice | None:
    try:
        root = defusedxml.ElementTree.fromstring(text)   # XXE-safe parser only
    except Exception:
        return None
    fmt = detect_format(root)
    if fmt is UNKNOWN: return None
    return MAPPERS[fmt](root)          # each builds a CompanyCandidate with
                                       # evidence=[FieldEvidence(field, quote=raw_value, confidence=1.0)]
```

Unrecognized-but-well-formed XML (`UNKNOWN` or mapper miss) → LLM fallback unchanged. `country` lands on `CompanyCandidate.country`; `currency` must be a 3-letter ISO code before reaching the candidate (normalize `TpoMoneda` absent → `CLP`; anything non-ISO → strip/uppercase and validate against the policy's `allowed_currencies` at rule time, not here).

Textract mapping (`AnalyzeExpense` synchronous; bytes in, `ExpenseDocuments[0].SummaryFields`):

| Textract TypeLabel | PaymentCandidate field |
|---|---|
| `VENDOR_NAME` | `payee_name` |
| `TAX_PAYER_ID` | `tax_id` |
| `TOTAL` / `OTHER` with `$` | `amount` (strip currency symbol) |
| `CURRENCY` (or symbol-derived) | `currency` |
| `INVOICE_RECEIPT_ID` | `invoice_number` |
| `DUE_DATE` / `INVOICE_RECEIPT_DATE` | `due_date` / `issue_date` |

Confidence per field = `ValueDetection.Confidence / 100`. Consider it sufficient only if `payee_name` **and** `amount` were found; otherwise return `None` (→ `no_info`). Client auth mirrors `bedrock.py`: `aioboto3.Session(profile_name, region)`, client `textract`.

Chain in `extract_candidate` (input already includes the selection from module 03):

```
primary.mime XML:
    parse_invoice_xml ─ success ──► candidate (note method="xml")
    └─ None ──► existing LLM extract on XML text (<attachment> block; method="xml_llm")
primary.mime PDF:
    pypdf text present ──► existing LLM path (text + base64 pdf block; method="pdf")
    └─ text empty OR InvoiceParseError ──► textract.analyze_expense(pdf bytes)
            └─ sufficient ──► candidate (method="textract")
            └─ None ──────────► raise InvoiceParseError (terminal)
all terminal failures ──► runner records extraction_failed ──► no_info
```

Runner change (currently `InvoiceParseError` → run FAILED → inbox ERROR): catch it inside `_decide_source` after extraction attempts, `insert_event(run_id, EXTRACTION_FAILED_STEP, {"reason": str(e), "methods_tried": [...]})`, and return without a decision so the run COMPLETES. `_resolve_status` distinguishes `no_invoice` (classification said not-a-bill; event `not_a_bill`) from `no_info` (classification said bill, extraction failed; event `extraction_failed`).

Secondary files never feed extraction; they are evidence only (module 05).

Self-check: each fixture maps deterministically with zero LLM calls (stub the gateway): `cfdi_mx.xml` → country MX + `@Moneda` currency + RFC as tax_id; `dte_cl.xml` → CL + CLP default when `TpoMoneda` absent + RUT; `ubl_co.xml` → CO from supplier `cbc:IdentificationCode` + `cbc:DocumentCurrencyCode`; `ubl_pe.xml` → PE (series `F001-…` invoice_number); `ubl_eu.xml` → EU country code; `unknown.xml` (well-formed, unrecognized ns) → LLM fallback fires; a blank page scanned to PDF (no text layer) → Textract path; corrupt PDF → run completes, inbox shows `no_info` (not `error`). Fixtures are minimal hand-crafted XMLs — exact namespaces/attributes from the table above; the real-world schemas are only needed for the mapped subset.

## Dependencies

- `defusedxml` (new). Textract IAM from module 01; aioboto3 already present.
- Module 03 (primary/secondary roles reach `extract_candidate` via the run's files).

## Integration Notes

- `PaymentCandidate` shape is untouched — downstream rules/checker/dedup see the same structure regardless of method; do not add a `method` field to the candidate itself (keep it in the `extracted`/`extraction_failed` event payloads).
- `no_info` must be added to the frontend `StatusBadge` map (module 06) in the same change-set.
- Textract failures (throttle/AccessDenied) must not crash the run: treat as method failure → `no_info` path, error reason in the event payload.
