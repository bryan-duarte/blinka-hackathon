import random
import unicodedata
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO
from typing import Literal
from xml.sax.saxutils import escape, quoteattr

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from PIL import Image, ImageDraw, ImageFont

DocumentLanguage = Literal["es", "pt", "en"]
NumberStyle = Literal["comma_thousands", "dot_thousands"]

ZIP_ENTRY_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ACCENT_RGB = (42, 75, 208)
INK_RGB = (30, 30, 30)
MUTED_RGB = (110, 110, 110)
HIDDEN_TEXT_RGB = (255, 255, 255)
HIDDEN_TEXT_SIZE = 4
PAGE_MARGIN_MM = 18
LINE_HEIGHT_MM = 6
TITLE_SIZE = 20
BODY_SIZE = 10
SMALL_SIZE = 8
TABLE_COLUMN_SHARES = (0.52, 0.12, 0.18, 0.18)
TEXT_ENCODING = "latin-1"
LATIN1_REPLACEMENTS = {"€": "EUR", "–": "-", "—": "-", "“": '"', "”": '"', "’": "'", "≈": "~"}
SCAN_CANVAS_SIZE = (1240, 1754)
SCAN_DPI = 150
SCAN_MARGIN_PX = 110
SCAN_FONT_SIZE = 30
SCAN_TITLE_FONT_SIZE = 46
SCAN_LINE_SPACING_PX = 46
SCAN_ROTATION_DEGREES = 0.6
SCAN_NOISE_POINTS = 2500
SCAN_NOISE_SEED = 7
SCAN_PAPER_GRAY = 246
SCAN_INK_GRAY = 35
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
DTE_INVOICE_TYPE = "33"
CFDI_INCOME_TYPE = "I"
MEXICAN_GENERIC_FOREIGN_RFC = "XEXX010101000"
_NEXT_LINE = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}

LABELS: dict[DocumentLanguage, dict[str, str]] = {
    "es": {
        "number": "N°",
        "issued": "Fecha de emisión",
        "due": "Fecha de vencimiento",
        "bill_to": "Facturar a",
        "description": "Descripción",
        "quantity": "Cant.",
        "unit": "Precio unit.",
        "amount": "Importe",
        "subtotal": "Subtotal",
        "total": "Total",
        "payment": "Datos de pago",
        "tax_id": "RUT/NIT/RFC",
    },
    "pt": {
        "number": "Nº",
        "issued": "Data de emissão",
        "due": "Vencimento",
        "bill_to": "Tomador",
        "description": "Descrição",
        "quantity": "Qtd.",
        "unit": "Valor unit.",
        "amount": "Valor",
        "subtotal": "Subtotal",
        "total": "Total",
        "payment": "Dados para pagamento",
        "tax_id": "CNPJ",
    },
    "en": {
        "number": "No.",
        "issued": "Issue date",
        "due": "Due date",
        "bill_to": "Bill to",
        "description": "Description",
        "quantity": "Qty",
        "unit": "Unit price",
        "amount": "Amount",
        "subtotal": "Subtotal",
        "total": "Total",
        "payment": "Payment details",
        "tax_id": "Tax ID",
    },
}


@dataclass(frozen=True)
class InvoiceLine:
    description: str
    quantity: Decimal
    unit_price: Decimal


@dataclass(frozen=True)
class InvoiceDocument:
    language: DocumentLanguage
    issuer_name: str
    issuer_tax_id: str | None
    issuer_address: str
    issuer_email: str | None
    bill_to: str
    title: str
    number: str
    issued_on: date
    due_on: date | None
    currency_label: str
    lines: list[InvoiceLine]
    payment_details: list[str]
    number_style: NumberStyle = "comma_thousands"
    amount_decimals: int = 2
    tax_label: str | None = None
    tax_rate: Decimal | None = None
    notes: list[str] = field(default_factory=list)
    hidden_text: str | None = None


def invoice_subtotal(document: InvoiceDocument) -> Decimal:
    return _rounded(
        sum((line.quantity * line.unit_price for line in document.lines), Decimal("0")),
        document.amount_decimals,
    )


def invoice_tax(document: InvoiceDocument) -> Decimal:
    if document.tax_rate is None:
        return Decimal("0")
    return _rounded(invoice_subtotal(document) * document.tax_rate, document.amount_decimals)


def invoice_total(document: InvoiceDocument) -> Decimal:
    return invoice_subtotal(document) + invoice_tax(document)


def format_document_amount(amount: Decimal, style: NumberStyle, decimals: int) -> str:
    comma_thousands = f"{amount:,.{decimals}f}"
    if style == "comma_thousands":
        return comma_thousands
    return comma_thousands.replace(",", "_").replace(".", ",").replace("_", ".")


def render_invoice_pdf(document: InvoiceDocument) -> bytes:
    labels = LABELS[document.language]
    pdf = _new_pdf(document.issued_on)
    _issuer_block(pdf, document, labels)
    _bill_to_block(pdf, document, labels)
    _lines_table(pdf, document, labels)
    _totals_block(pdf, document, labels)
    _payment_block(pdf, document, labels)
    _notes_block(pdf, document)
    if document.hidden_text:
        _hidden_block(pdf, document.hidden_text)
    return bytes(pdf.output())


def render_scanned_invoice_pdf(document: InvoiceDocument) -> bytes:
    scan = _scanned_page(invoice_text_lines(document))
    pdf = FPDF(format="A4")
    pdf.set_creation_date(_creation_date(document.issued_on))
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.image(scan, x=0, y=0, w=A4_WIDTH_MM, h=A4_HEIGHT_MM)
    return bytes(pdf.output())


def invoice_text_lines(document: InvoiceDocument) -> list[str]:
    labels = LABELS[document.language]
    return [
        document.issuer_name,
        *([f"{labels['tax_id']}: {document.issuer_tax_id}"] if document.issuer_tax_id else []),
        document.issuer_address,
        "",
        f"{document.title} {labels['number']} {document.number}",
        f"{labels['issued']}: {document.issued_on.isoformat()}",
        *([f"{labels['due']}: {document.due_on.isoformat()}"] if document.due_on else []),
        f"{labels['bill_to']}: {document.bill_to}",
        "",
        *(
            f"- {line.description} x{line.quantity:g}: {document.currency_label} "
            f"{_document_amount(document, line.quantity * line.unit_price)}"
            for line in document.lines
        ),
        "",
        f"{labels['total']}: {_total_text(document)}",
        "",
        f"{labels['payment']}:",
        *document.payment_details,
    ]


def render_xml_cfdi(document: InvoiceDocument, receiver_name: str) -> bytes:
    subtotal, tax, total = (
        invoice_subtotal(document),
        invoice_tax(document),
        invoice_total(document),
    )
    payment_terms = f"Vencimiento {document.due_on.isoformat()}" if document.due_on else "Contado"
    concepts = "\n".join(
        f'    <cfdi:Concepto Cantidad="{line.quantity:g}" '
        f"Descripcion={quoteattr(line.description)} "
        f'ValorUnitario="{line.unit_price:.2f}" Importe="{line.quantity * line.unit_price:.2f}"/>'
        for line in document.lines
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" \
xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" Version="4.0" \
Folio={quoteattr(document.number)} Fecha="{document.issued_on.isoformat()}T10:00:00" \
Moneda="MXN" SubTotal="{subtotal:.2f}" Total="{total:.2f}" TipoDeComprobante="{CFDI_INCOME_TYPE}" \
CondicionesDePago={quoteattr(payment_terms)} MetodoPago="PPD" FormaPago="03">
  <cfdi:Emisor Rfc={quoteattr(document.issuer_tax_id or "")} \
Nombre={quoteattr(document.issuer_name)} RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{MEXICAN_GENERIC_FOREIGN_RFC}" Nombre={quoteattr(receiver_name)} \
UsoCFDI="G03"/>
  <cfdi:Conceptos>
{concepts}
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="{tax:.2f}"/>
</cfdi:Comprobante>
"""
    return xml.encode()


def render_xml_dte(document: InvoiceDocument) -> bytes:
    net, tax, total = invoice_subtotal(document), invoice_tax(document), invoice_total(document)
    due_element = (
        f"\n        <FchVenc>{document.due_on.isoformat()}</FchVenc>" if document.due_on else ""
    )
    tax_rate_percent = (document.tax_rate or Decimal("0")) * 100
    xml = f"""<?xml version="1.0" encoding="ISO-8859-1"?>
<DTE xmlns="http://www.sii.cl/SiiDte" version="1.0">
  <Documento ID="F{DTE_INVOICE_TYPE}T{escape(document.number)}">
    <Encabezado>
      <IdDoc>
        <TipoDTE>{DTE_INVOICE_TYPE}</TipoDTE>
        <Folio>{escape(document.number)}</Folio>
        <FchEmis>{document.issued_on.isoformat()}</FchEmis>{due_element}
      </IdDoc>
      <Emisor>
        <RUTEmisor>{escape((document.issuer_tax_id or "").replace(".", ""))}</RUTEmisor>
        <RznSoc>{escape(document.issuer_name)}</RznSoc>
        <GiroEmis>Servicios profesionales</GiroEmis>
        <CorreoEmisor>{escape(document.issuer_email or "")}</CorreoEmisor>
      </Emisor>
      <Totales>
        <MntNeto>{net:.0f}</MntNeto>
        <TasaIVA>{tax_rate_percent:.0f}</TasaIVA>
        <IVA>{tax:.0f}</IVA>
        <MntTotal>{total:.0f}</MntTotal>
      </Totales>
    </Encabezado>
  </Documento>
</DTE>
"""
    return xml.encode(TEXT_ENCODING)


def zip_archive(members: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for member_name, member_content in members.items():
            entry = zipfile.ZipInfo(member_name, date_time=ZIP_ENTRY_TIMESTAMP)
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, member_content)
    return buffer.getvalue()


def _new_pdf(issued_on: date) -> FPDF:
    pdf = FPDF(format="A4")
    pdf.set_creation_date(_creation_date(issued_on))
    pdf.set_margins(PAGE_MARGIN_MM, PAGE_MARGIN_MM, PAGE_MARGIN_MM)
    pdf.set_auto_page_break(auto=True, margin=PAGE_MARGIN_MM)
    pdf.add_page()
    return pdf


def _issuer_block(pdf: FPDF, document: InvoiceDocument, labels: dict[str, str]) -> None:
    top = pdf.get_y()
    half_width = pdf.epw / 2
    _set_text(pdf, BODY_SIZE, style="B")
    pdf.cell(half_width, LINE_HEIGHT_MM, _latin1(document.issuer_name), **_NEXT_LINE)
    _set_text(pdf, SMALL_SIZE, color=MUTED_RGB)
    issuer_lines = [
        *([f"{labels['tax_id']}: {document.issuer_tax_id}"] if document.issuer_tax_id else []),
        document.issuer_address,
        *([document.issuer_email] if document.issuer_email else []),
    ]
    for issuer_line in issuer_lines:
        pdf.cell(half_width, LINE_HEIGHT_MM - 1, _latin1(issuer_line), **_NEXT_LINE)
    issuer_bottom = pdf.get_y()
    pdf.set_xy(PAGE_MARGIN_MM + half_width, top)
    _set_text(pdf, TITLE_SIZE, style="B", color=ACCENT_RGB)
    pdf.cell(half_width, LINE_HEIGHT_MM + 4, _latin1(document.title), align="R", **_NEXT_LINE)
    _set_text(pdf, BODY_SIZE)
    title_lines = [
        f"{labels['number']} {document.number}",
        f"{labels['issued']}: {document.issued_on.isoformat()}",
        *([f"{labels['due']}: {document.due_on.isoformat()}"] if document.due_on else []),
    ]
    for title_line in title_lines:
        pdf.set_x(PAGE_MARGIN_MM + half_width)
        pdf.cell(half_width, LINE_HEIGHT_MM, _latin1(title_line), align="R", **_NEXT_LINE)
    pdf.set_y(max(issuer_bottom, pdf.get_y()) + 4)
    _hairline(pdf)


def _bill_to_block(pdf: FPDF, document: InvoiceDocument, labels: dict[str, str]) -> None:
    _set_text(pdf, SMALL_SIZE, style="B", color=MUTED_RGB)
    pdf.cell(0, LINE_HEIGHT_MM, _latin1(labels["bill_to"].upper()), **_NEXT_LINE)
    _set_text(pdf, BODY_SIZE)
    pdf.multi_cell(0, LINE_HEIGHT_MM, _latin1(document.bill_to), **_NEXT_LINE)
    pdf.ln(4)


def _lines_table(pdf: FPDF, document: InvoiceDocument, labels: dict[str, str]) -> None:
    widths = [pdf.epw * share for share in TABLE_COLUMN_SHARES]
    headers = (labels["description"], labels["quantity"], labels["unit"], labels["amount"])
    _set_text(pdf, SMALL_SIZE, style="B", color=MUTED_RGB)
    for width, header, align in zip(widths, headers, ("L", "R", "R", "R"), strict=True):
        pdf.cell(width, LINE_HEIGHT_MM, _latin1(header.upper()), align=align)
    pdf.ln(LINE_HEIGHT_MM)
    _hairline(pdf)
    _set_text(pdf, BODY_SIZE)
    for line in document.lines:
        cell_texts = (
            line.description,
            f"{line.quantity:g}",
            _document_amount(document, line.unit_price),
            _document_amount(document, line.quantity * line.unit_price),
        )
        for width, cell_text, align in zip(widths, cell_texts, ("L", "R", "R", "R"), strict=True):
            pdf.cell(width, LINE_HEIGHT_MM + 1, _latin1(cell_text), align=align)
        pdf.ln(LINE_HEIGHT_MM + 1)
    _hairline(pdf)


def _totals_block(pdf: FPDF, document: InvoiceDocument, labels: dict[str, str]) -> None:
    label_width, amount_width = pdf.epw * 0.75, pdf.epw * 0.25
    amount_rows = [(labels["subtotal"], invoice_subtotal(document))]
    if document.tax_label:
        amount_rows.append((document.tax_label, invoice_tax(document)))
    _set_text(pdf, BODY_SIZE)
    for label, amount in amount_rows:
        pdf.cell(label_width, LINE_HEIGHT_MM, _latin1(label), align="R")
        amount_text = _latin1(_document_amount(document, amount))
        pdf.cell(amount_width, LINE_HEIGHT_MM, amount_text, align="R", **_NEXT_LINE)
    _set_text(pdf, BODY_SIZE + 2, style="B")
    total_text = _total_text(document)
    pdf.cell(label_width, LINE_HEIGHT_MM + 2, _latin1(labels["total"]), align="R")
    pdf.cell(amount_width, LINE_HEIGHT_MM + 2, _latin1(total_text), align="R", **_NEXT_LINE)
    pdf.ln(6)


def _payment_block(pdf: FPDF, document: InvoiceDocument, labels: dict[str, str]) -> None:
    if not document.payment_details:
        return
    _set_text(pdf, SMALL_SIZE, style="B", color=MUTED_RGB)
    pdf.cell(0, LINE_HEIGHT_MM, _latin1(labels["payment"].upper()), **_NEXT_LINE)
    _set_text(pdf, BODY_SIZE)
    for detail in document.payment_details:
        pdf.cell(0, LINE_HEIGHT_MM, _latin1(detail), **_NEXT_LINE)
    pdf.ln(4)


def _notes_block(pdf: FPDF, document: InvoiceDocument) -> None:
    _set_text(pdf, SMALL_SIZE, color=MUTED_RGB)
    for note in document.notes:
        pdf.multi_cell(0, LINE_HEIGHT_MM - 1, _latin1(note), **_NEXT_LINE)


def _hidden_block(pdf: FPDF, hidden_text: str) -> None:
    _set_text(pdf, HIDDEN_TEXT_SIZE, color=HIDDEN_TEXT_RGB)
    pdf.multi_cell(0, HIDDEN_TEXT_SIZE / 2, _latin1(hidden_text), **_NEXT_LINE)


def _creation_date(issued_on: date) -> datetime:
    return datetime.combine(issued_on, time(), tzinfo=UTC)


def _hairline(pdf: FPDF) -> None:
    pdf.set_draw_color(*MUTED_RGB)
    pdf.set_line_width(0.1)
    y = pdf.get_y()
    pdf.line(PAGE_MARGIN_MM, y, PAGE_MARGIN_MM + pdf.epw, y)
    pdf.ln(2)


def _set_text(
    pdf: FPDF, size: float, style: str = "", color: tuple[int, int, int] = INK_RGB
) -> None:
    pdf.set_font("Helvetica", style=style, size=size)
    pdf.set_text_color(*color)


def _scanned_page(lines: list[str]) -> Image.Image:
    page = Image.new("L", SCAN_CANVAS_SIZE, color=SCAN_PAPER_GRAY)
    draw = ImageDraw.Draw(page)
    body_font = ImageFont.load_default(size=SCAN_FONT_SIZE)
    title_font = ImageFont.load_default(size=SCAN_TITLE_FONT_SIZE)
    y = SCAN_MARGIN_PX
    for index, line in enumerate(lines):
        font = title_font if index == 0 else body_font
        draw.text((SCAN_MARGIN_PX, y), _without_accents(line), fill=SCAN_INK_GRAY, font=font)
        y += SCAN_LINE_SPACING_PX + (SCAN_TITLE_FONT_SIZE - SCAN_FONT_SIZE if index == 0 else 0)
    noise = random.Random(SCAN_NOISE_SEED)
    for _ in range(SCAN_NOISE_POINTS):
        point = (noise.randrange(SCAN_CANVAS_SIZE[0]), noise.randrange(SCAN_CANVAS_SIZE[1]))
        page.putpixel(point, noise.randrange(150, 230))
    rotated = page.rotate(
        SCAN_ROTATION_DEGREES, resample=Image.Resampling.BICUBIC, fillcolor=SCAN_PAPER_GRAY
    )
    rotated.info["dpi"] = (SCAN_DPI, SCAN_DPI)
    return rotated.convert("RGB")


def _total_text(document: InvoiceDocument) -> str:
    return f"{document.currency_label} {_document_amount(document, invoice_total(document))}"


def _document_amount(document: InvoiceDocument, amount: Decimal) -> str:
    return format_document_amount(amount, document.number_style, document.amount_decimals)


def _rounded(amount: Decimal, decimals: int) -> Decimal:
    return amount.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def _without_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _latin1(text: str) -> str:
    for character, replacement in LATIN1_REPLACEMENTS.items():
        text = text.replace(character, replacement)
    return text.encode(TEXT_ENCODING, "replace").decode(TEXT_ENCODING)
