"""Write one e-invoice ZIP (XML + PDF) per supported country to <repo>/samples/invoices/zip/.

Run (from backend/): uv run python -m scripts.generate_country_zips
"""

from pathlib import Path

from modules.files.archives import expand_zip
from modules.inbox.samples import minimal_pdf, zip_archive
from modules.invoice_ingestor.xml_parser import parse_invoice_xml

BACKEND_DIR = Path(__file__).resolve().parents[1]
XML_FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures" / "xml"
OUTPUT_DIR = BACKEND_DIR.parent / "samples" / "invoices" / "zip"
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
