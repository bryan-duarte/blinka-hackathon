from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from contracts.payment_candidates import XmlInvoiceFormat
from modules.invoice_ingestor.xml_parser import parse_invoice_xml
from modules.payments.fx import names_currency_explicitly

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "xml"
BILLION_LAUGHS = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;">]>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Total="1">&lol2;</cfdi:Comprobante>"""
EXTERNAL_ENTITY = b"""<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Total="1">&xxe;</cfdi:Comprobante>"""


def _fixture(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


@pytest.mark.parametrize(
    (
        "fixture",
        "expected_format",
        "payee_name",
        "tax_id",
        "amount",
        "currency",
        "issuer_tax_country",
        "payee_country",
        "invoice_number",
    ),
    [
        (
            "cfdi_mx.xml",
            XmlInvoiceFormat.CFDI_MX,
            "Servicios Digitales Aztec SA de CV",
            "SDA010203AB1",
            Decimal("11600.00"),
            "MXN",
            "MX",
            None,
            "A-1024",
        ),
        (
            "dte_cl.xml",
            XmlInvoiceFormat.DTE_CL,
            "Servicios del Sur SpA",
            "76543210-K",
            Decimal("499800"),
            "CLP",
            "CL",
            None,
            "33-5532",
        ),
        (
            "ubl_co.xml",
            XmlInvoiceFormat.UBL,
            "Andes Software SAS",
            "900123456",
            Decimal("2380000.00"),
            "COP",
            "CO",
            "CO",
            "SETP990000123",
        ),
        (
            "ubl_pe.xml",
            XmlInvoiceFormat.UBL,
            "Inca Cloud SAC",
            "20512345678",
            Decimal("1180.00"),
            "PEN",
            "PE",
            None,
            "F001-000123",
        ),
        (
            "ubl_eu.xml",
            XmlInvoiceFormat.UBL,
            "Berlin Data GmbH",
            "DE123456789",
            Decimal("595.00"),
            "EUR",
            None,
            "DE",
            "RE-2026-0042",
        ),
        (
            "cii_eu.xml",
            XmlInvoiceFormat.CII,
            "Lumiere Conseil SARL",
            "FR40303265045",
            Decimal("1440.00"),
            "EUR",
            None,
            "FR",
            "FX-2026-118",
        ),
    ],
)
def test_recognized_formats_map_deterministically(
    fixture: str,
    expected_format: XmlInvoiceFormat,
    payee_name: str,
    tax_id: str,
    amount: Decimal,
    currency: str,
    issuer_tax_country: str | None,
    payee_country: str | None,
    invoice_number: str,
) -> None:
    parsed = parse_invoice_xml(_fixture(fixture))

    assert parsed is not None
    assert parsed.format is expected_format
    fields = parsed.fields
    assert fields.payee_name == payee_name
    assert fields.tax_id == tax_id
    assert fields.amount == amount
    assert fields.currency == currency
    assert fields.issuer_tax_country == issuer_tax_country
    assert fields.payee_country == payee_country
    assert fields.invoice_number == invoice_number
    assert all(evidence.confidence == 1.0 for evidence in fields.evidence)


def test_dte_dates_and_default_currency() -> None:
    parsed = parse_invoice_xml(_fixture("dte_cl.xml"))

    assert parsed is not None
    assert parsed.fields.issue_date == date(2026, 10, 2)
    assert parsed.fields.due_date == date(2026, 11, 1)
    currency_quotes = [
        evidence.quote for evidence in parsed.fields.evidence if evidence.field == "currency"
    ]
    assert parsed.fields.currency == "CLP"
    assert currency_quotes and all("CLP" in quote for quote in currency_quotes)
    assert names_currency_explicitly(currency_quotes[0], "CLP")


def test_cii_compact_dates() -> None:
    parsed = parse_invoice_xml(_fixture("cii_eu.xml"))

    assert parsed is not None
    assert parsed.fields.issue_date == date(2026, 10, 4)
    assert parsed.fields.due_date == date(2026, 11, 3)


def test_unknown_xml_yields_partial_hints_without_payee() -> None:
    parsed = parse_invoice_xml(_fixture("unknown.xml"))

    assert parsed is not None
    assert parsed.format is XmlInvoiceFormat.UNKNOWN
    assert not parsed.fields.is_sufficient
    assert parsed.origin is not None
    assert parsed.fields.issuer_tax_country == "BR"


def test_unknown_xml_reads_generic_currency_and_tax_id() -> None:
    generic_invoice = b"""<?xml version="1.0"?>
<Invoice xmlns="https://schemas.vendor-erp.io/invoice/v2">
  <Supplier><Name>Lakeview Analytics LLC</Name><TaxID>12-3456789</TaxID>
    <Address><CountryCode>US</CountryCode></Address></Supplier>
  <Total currencyID="usd">980.00</Total>
</Invoice>"""

    parsed = parse_invoice_xml(generic_invoice)

    assert parsed is not None
    assert parsed.fields.currency == "USD"
    assert parsed.fields.payee_country is None
    assert parsed.fields.tax_id == "12-3456789"


def test_commercial_namespace_domain_is_not_a_country_signal() -> None:
    parsed = parse_invoice_xml(
        b'<Invoice xmlns="https://acme.co/invoice"><Total>1</Total></Invoice>'
    )

    assert parsed is not None
    assert parsed.fields.issuer_tax_country is None


def test_non_bill_dte_type_falls_back() -> None:
    credit_note = _fixture("dte_cl.xml").replace(b"<TipoDTE>33</TipoDTE>", b"<TipoDTE>61</TipoDTE>")

    assert parse_invoice_xml(credit_note) is None


@pytest.mark.parametrize("hostile_xml", [BILLION_LAUGHS, EXTERNAL_ENTITY, b"<not-xml"])
def test_hostile_or_broken_xml_is_rejected(hostile_xml: bytes) -> None:
    assert parse_invoice_xml(hostile_xml) is None


def test_cfdi_credit_note_falls_back() -> None:
    credit_note = _fixture("cfdi_mx.xml").replace(
        b'TipoDeComprobante="I"', b'TipoDeComprobante="E"'
    )

    assert parse_invoice_xml(credit_note) is None


UBL_NAMESPACES = (
    'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"'
)
DIAN_INVOICE = (
    f"<Invoice {UBL_NAMESPACES} "
    'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
    'xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1">'
    "<ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent><sts:DianExtensions/>"
    "</ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>"
    "<cbc:CustomizationID>10</cbc:CustomizationID><cbc:ID>SETP990000001</cbc:ID></Invoice>"
)
COUNTRY_ORIGIN_SAMPLES = {
    "mx-cfdi": (
        b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
        b'TipoDeComprobante="I" Total="1"/>',
        "MX",
        "SAT",
    ),
    "cl-envio-dte": (
        b'<EnvioDTE xmlns="http://www.sii.cl/SiiDte"><SetDTE><DTE><Documento><Encabezado>'
        b"<IdDoc><TipoDTE>33</TipoDTE></IdDoc></Encabezado></Documento></DTE></SetDTE>"
        b"</EnvioDTE>",
        "CL",
        "SII",
    ),
    "co-attached-document": (
        (
            '<AttachedDocument xmlns="urn:oasis:names:specification:ubl:schema:xsd:'
            'AttachedDocument-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:'
            'CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:'
            'xsd:CommonBasicComponents-2"><cac:Attachment><cac:ExternalReference>'
            f'<cbc:Description><![CDATA[<?xml version="1.0" encoding="UTF-8"?>{DIAN_INVOICE}]]>'
            "</cbc:Description></cac:ExternalReference></cac:Attachment></AttachedDocument>"
        ).encode(),
        "CO",
        "DIAN",
    ),
    "pe-ubl-sac": (
        (
            f'<Invoice {UBL_NAMESPACES} xmlns:sac="urn:sunat:names:specification:ubl:peru:'
            'schema:xsd:SunatAggregateComponents-1"><sac:AdditionalInformation/></Invoice>'
        ).encode(),
        "PE",
        "SUNAT",
    ),
    "ec-sri": (
        b'<factura id="comprobante" version="1.1.0"><infoTributaria><ruc>1790012345001</ruc>'
        b"</infoTributaria></factura>",
        "EC",
        "SRI",
    ),
    "ec-sri-authorization": (
        b"<autorizacion><estado>AUTORIZADO</estado><comprobante><![CDATA["
        b'<factura id="comprobante" version="1.1.0"><infoTributaria/></factura>]]>'
        b"</comprobante></autorizacion>",
        "EC",
        "SRI",
    ),
    "br-nfe": (
        b'<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe/></NFe></nfeProc>',
        "BR",
        "SEFAZ",
    ),
    "uy-cfe": (b'<CFE xmlns="http://cfe.dgi.gub.uy"><eFact/></CFE>', "UY", "DGI"),
    "cr-hacienda": (
        b'<FacturaElectronica xmlns="https://cdn.comprobanteselectronicos.go.cr/xml-schemas/'
        b'v4.4/facturaElectronica"/>',
        "CR",
        "Hacienda",
    ),
    "gt-fel": (
        b'<dte:GTDocumento xmlns:dte="http://www.sat.gob.gt/dte/fel/0.2.0"><dte:SAT/>'
        b"</dte:GTDocumento>",
        "GT",
        "SAT",
    ),
    "py-sifen": (b'<rDE xmlns="http://ekuatia.set.gov.py/sifen/xsd"><DE/></rDE>', "PY", "SET"),
    "do-ecf": (
        b"<ECF><Encabezado><IdDoc><TipoeCF>31</TipoeCF></IdDoc></Encabezado></ECF>",
        "DO",
        "DGII",
    ),
    "it-fatturapa": (
        b'<p:FatturaElettronica versione="FPR12" xmlns:p="http://ivaservizi.agenziaentrate'
        b'.gov.it/docs/xsd/fatture/v1.2"/>',
        "IT",
        "Agenzia delle Entrate",
    ),
    "es-facturae": (
        b'<fe:Facturae xmlns:fe="http://www.facturae.gob.es/formato/Versiones/'
        b'Facturaev3_2_2.xml"/>',
        "ES",
        "AEAT",
    ),
    "pl-ksef": (
        b'<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/"/>',
        "PL",
        "Ministerstwo Finansów",
    ),
    "gr-mydata": (
        b'<InvoicesDoc xmlns="http://www.aade.gr/myDATA/invoice/v1.0"/>',
        "GR",
        "AADE",
    ),
    "tr-ubl": (
        f"<Invoice {UBL_NAMESPACES}><cbc:CustomizationID>TR1.2</cbc:CustomizationID>"
        "<cbc:ProfileID>TEMELFATURA</cbc:ProfileID></Invoice>".encode(),
        "TR",
        "GİB",
    ),
    "sa-zatca": (
        (
            f"<Invoice {UBL_NAMESPACES}><cbc:ProfileID>reporting:1.0</cbc:ProfileID></Invoice>"
        ).encode(),
        "SA",
        "ZATCA",
    ),
    "de-xrechnung": (
        f"<Invoice {UBL_NAMESPACES}><cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant"
        "#urn:xeinkauf.de:kosit:xrechnung_3.0</cbc:CustomizationID></Invoice>".encode(),
        "DE",
        "KoSIT",
    ),
}


@pytest.mark.parametrize(
    ("xml_content", "expected_country", "expected_authority"),
    list(COUNTRY_ORIGIN_SAMPLES.values()),
    ids=list(COUNTRY_ORIGIN_SAMPLES),
)
def test_source_country_is_detected_from_national_standard(
    xml_content: bytes, expected_country: str, expected_authority: str
) -> None:
    parsed = parse_invoice_xml(xml_content)

    assert parsed is not None
    assert parsed.origin is not None
    assert parsed.origin.country == expected_country
    assert parsed.origin.authority == expected_authority
    assert parsed.fields.issuer_tax_country == expected_country


def test_peppol_ubl_without_national_marker_uses_supplier_address() -> None:
    parsed = parse_invoice_xml(_fixture("ubl_eu.xml"))

    assert parsed is not None
    assert parsed.origin is None
    assert parsed.fields.issuer_tax_country is None
    assert parsed.fields.payee_country == "DE"


def test_attached_document_is_unwrapped_for_field_mapping() -> None:
    parsed = parse_invoice_xml(COUNTRY_ORIGIN_SAMPLES["co-attached-document"][0])

    assert parsed is not None
    assert parsed.format is XmlInvoiceFormat.UBL
    assert parsed.fields.invoice_number == "SETP990000001"
