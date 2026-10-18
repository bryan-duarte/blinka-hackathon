"""Write one e-invoice ZIP (XML + PDF) per supported country to <repo>/samples/invoices/zip/.

Run (from backend/): uv run python -m scripts.generate_country_zips
"""

from pathlib import Path

from modules.demo.documents import zip_archive
from modules.files.archives import expand_zip
from modules.invoice_ingestor.xml_parser import parse_invoice_xml

BACKEND_DIR = Path(__file__).resolve().parents[1]
XML_FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures" / "xml"
OUTPUT_DIR = BACKEND_DIR.parent / "samples" / "invoices" / "zip"
PDF_FONT_SIZE = 11
PDF_LINE_HEIGHT = 16
PDF_LEFT_MARGIN = 56
PDF_TOP_OFFSET = 780
PDF_PAGE_BOX = "0 0 612 842"
PDF_TEXT_ENCODING = "latin-1"
COUNTRY_SAMPLES = {
    "mx-cfdi-aztec": "cfdi_mx.xml",
    "cl-dte-sur": "dte_cl.xml",
    "co-ubl-andes": "ubl_co.xml",
    "pe-ubl-inca": "ubl_pe.xml",
    "de-ubl-berlin": "ubl_eu.xml",
    "fr-cii-lumiere": "cii_eu.xml",
}


def _pdf_lines(xml_content: bytes) -> list[str]:
    parsed_invoice = parse_invoice_xml(xml_content)
    if parsed_invoice is None:
        raise SystemExit("fixture is not a recognized e-invoice")
    fields = parsed_invoice.fields
    return [
        fields.payee_name or "",
        f"ID fiscal: {fields.tax_id}",
        f"Factura N°: {fields.invoice_number}",
        f"Fecha de emisión: {fields.issue_date}",
        f"Fecha de vencimiento: {fields.due_date}",
        "",
        f"Total: {fields.currency} {fields.amount}",
    ]


def minimal_pdf(lines: list[str]) -> bytes:
    text_operations = [
        f"BT /F1 {PDF_FONT_SIZE} Tf {PDF_LEFT_MARGIN} {PDF_TOP_OFFSET} Td {PDF_LINE_HEIGHT} TL",
        *(f"({_escape_pdf_text(line)}) Tj T*" for line in lines),
        "ET",
    ]
    content_stream = "\n".join(text_operations).encode(PDF_TEXT_ENCODING)
    pdf_objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [{PDF_PAGE_BOX}] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        f"<< /Length {len(content_stream)} >>\nstream\n".encode() + content_stream + b"\nendstream",
    ]
    document = bytearray(b"%PDF-1.4\n")
    object_offsets = []
    for object_number, object_body in enumerate(pdf_objects, start=1):
        object_offsets.append(len(document))
        document += f"{object_number} 0 obj\n".encode() + object_body + b"\nendobj\n"
    cross_reference_offset = len(document)
    object_count = len(pdf_objects) + 1
    document += f"xref\n0 {object_count}\n0000000000 65535 f \n".encode()
    document += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in object_offsets)
    document += (
        f"trailer\n<< /Size {object_count} /Root 1 0 R >>\n"
        f"startxref\n{cross_reference_offset}\n%%EOF\n"
    ).encode()
    return bytes(document)


def _escape_pdf_text(line: str) -> str:
    return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for sample_name, fixture_name in COUNTRY_SAMPLES.items():
        xml_content = (XML_FIXTURES_DIR / fixture_name).read_bytes()
        archive = zip_archive(
            {
                f"{sample_name}.xml": xml_content,
                f"{sample_name}.pdf": minimal_pdf(_pdf_lines(xml_content)),
            }
        )
        expand_zip(archive)
        (OUTPUT_DIR / f"{sample_name}.zip").write_bytes(archive)


if __name__ == "__main__":
    main()
