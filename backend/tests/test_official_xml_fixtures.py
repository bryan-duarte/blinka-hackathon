from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from contracts.payment_candidates import DocumentIssuer, XmlInvoiceFormat
from core.tax_jurisdictions import tax_id_fits_country
from modules.invoice_ingestor.xml_parser import parse_invoice_xml

OFFICIAL_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "xml" / "official"
SELLER = DocumentIssuer.SELLER
BUYER = DocumentIssuer.BUYER


@dataclass(frozen=True)
class ExpectedOrigin:
    country: str
    authority: str
    issued_by: DocumentIssuer = SELLER


@dataclass(frozen=True)
class ExpectedInvoice:
    invoice_format: XmlInvoiceFormat
    origin: ExpectedOrigin | None
    issuer_tax_country: str | None
    payee_country: str | None = None
    payee_name: str | None = None
    tax_id: str | None = None
    amount: Decimal | None = None
    currency: str | None = None


UNKNOWN = XmlInvoiceFormat.UNKNOWN
OFFICIAL_INVOICES: dict[str, ExpectedInvoice] = {
    "mx_cfdi40_ingreso.xml": ExpectedInvoice(
        XmlInvoiceFormat.CFDI_MX,
        ExpectedOrigin("MX", "SAT"),
        "MX",
        payee_name="ESCUELA KEMPER URGATE",
        tax_id="EKU9003173C9",
        amount=Decimal("232.00"),
        currency="MXN",
    ),
    "mx_cfdi40_exportacion.xml": ExpectedInvoice(
        XmlInvoiceFormat.CFDI_MX,
        ExpectedOrigin("MX", "SAT"),
        "MX",
        payee_name="ESCUELA KEMPER URGATE",
        tax_id="EKU9003173C9",
        currency="MXN",
    ),
    "mx_cfdi33_ingreso.xml": ExpectedInvoice(
        XmlInvoiceFormat.CFDI_MX,
        ExpectedOrigin("MX", "SAT"),
        "MX",
        payee_name="PROMOTORA OTIR SA DE CV",
        tax_id="POT9207213D6",
        amount=Decimal("2010.01"),
        currency="MXN",
    ),
    "cl_dte33_envio_sii.xml": ExpectedInvoice(
        XmlInvoiceFormat.DTE_CL,
        ExpectedOrigin("CL", "SII"),
        "CL",
        payee_name="RUT DE PRUEBA",
        tax_id="97975000-5",
        amount=Decimal("119000"),
        currency="CLP",
    ),
    "cl_dte46_factura_compra.xml": ExpectedInvoice(
        XmlInvoiceFormat.DTE_CL,
        ExpectedOrigin("CL", "SII", BUYER),
        None,
        payee_name="PROVEEDOR SIN FACTURA LTDA",
        tax_id="77777777-7",
        amount=Decimal("100000"),
        currency="CLP",
    ),
    "co_dian_attached_document.xml": ExpectedInvoice(
        XmlInvoiceFormat.UBL,
        ExpectedOrigin("CO", "DIAN"),
        "CO",
        payee_country="CO",
        payee_name="PROVEEDOR EJEMPLO S.A.S.",
        tax_id="900000002",
        amount=Decimal("623113.00"),
        currency="COP",
    ),
    "co_dian_documento_soporte.xml": ExpectedInvoice(
        XmlInvoiceFormat.UBL,
        ExpectedOrigin("CO", "DIAN", BUYER),
        None,
        payee_country="CO",
        payee_name="hgyujk hjijok",
        tax_id="901228165",
        amount=Decimal("17850.00"),
        currency="COP",
    ),
    "pe_sunat_factura_ubl21.xml": ExpectedInvoice(
        XmlInvoiceFormat.UBL,
        ExpectedOrigin("PE", "SUNAT"),
        "PE",
        payee_country="PE",
        payee_name="mi razon social",
        tax_id="12345678912",
        amount=Decimal("11.8"),
        currency="PEN",
    ),
    "ec_sri_factura.xml": ExpectedInvoice(
        XmlInvoiceFormat.SRI_EC,
        ExpectedOrigin("EC", "SRI"),
        "EC",
        payee_name="razonSocial0",
        tax_id="0000000000001",
        amount=Decimal("50.00"),
    ),
    "ec_sri_liquidacion_compra.xml": ExpectedInvoice(
        XmlInvoiceFormat.SRI_EC,
        ExpectedOrigin("EC", "SRI", BUYER),
        None,
        payee_name="Proveedor de Prueba",
        tax_id="0102030405",
        amount=Decimal("112.00"),
        currency="USD",
    ),
    "br_nfe_nfeproc.xml": ExpectedInvoice(UNKNOWN, ExpectedOrigin("BR", "SEFAZ"), "BR"),
    "br_nfse_abrasf.xml": ExpectedInvoice(UNKNOWN, ExpectedOrigin("BR", "ABRASF"), "BR"),
    "uy_cfe_envio.xml": ExpectedInvoice(UNKNOWN, ExpectedOrigin("UY", "DGI"), "UY"),
    "cr_factura_electronica_44.xml": ExpectedInvoice(
        UNKNOWN, ExpectedOrigin("CR", "Hacienda"), "CR"
    ),
    "gt_fel_factura.xml": ExpectedInvoice(UNKNOWN, ExpectedOrigin("GT", "SAT"), "GT"),
    "py_sifen_factura.xml": ExpectedInvoice(UNKNOWN, ExpectedOrigin("PY", "SET"), "PY"),
    "do_ecf_consumo.xml": ExpectedInvoice(UNKNOWN, ExpectedOrigin("DO", "DGII"), "DO"),
    "bo_siat_compra_venta.xml": ExpectedInvoice(UNKNOWN, ExpectedOrigin("BO", "SIN"), "BO"),
    "it_fatturapa_fpr12.xml": ExpectedInvoice(
        UNKNOWN, ExpectedOrigin("IT", "Agenzia delle Entrate"), "IT", currency="EUR"
    ),
    "es_facturae_31.xml": ExpectedInvoice(
        UNKNOWN, ExpectedOrigin("ES", "AEAT"), "ES", currency="EUR"
    ),
    "pl_ksef_fa3.xml": ExpectedInvoice(
        UNKNOWN, ExpectedOrigin("PL", "Ministerstwo Finansów"), "PL"
    ),
    "gr_mydata_invoices_doc.xml": ExpectedInvoice(UNKNOWN, ExpectedOrigin("GR", "AADE"), "GR"),
    "hu_nav_invoice_data.xml": ExpectedInvoice(UNKNOWN, ExpectedOrigin("HU", "NAV"), "HU"),
    "tr_ubltr_temel_fatura.xml": ExpectedInvoice(
        XmlInvoiceFormat.UBL,
        ExpectedOrigin("TR", "GİB"),
        "TR",
        payee_name="AAA Anonim Şirketi",
        tax_id="1288331521",
        amount=Decimal("17.88"),
        currency="TRY",
    ),
    "tr_ubltr_ticari_fatura.xml": ExpectedInvoice(
        XmlInvoiceFormat.UBL,
        ExpectedOrigin("TR", "GİB"),
        "TR",
        payee_name="AAA Anonim Şirketi",
        tax_id="1288331521",
        amount=Decimal("29755.47"),
        currency="TRY",
    ),
    "sa_zatca_standard_invoice.xml": ExpectedInvoice(
        XmlInvoiceFormat.UBL,
        ExpectedOrigin("SA", "ZATCA"),
        "SA",
        payee_country="SA",
        tax_id="311111111101113",
        amount=Decimal("4.60"),
        currency="SAR",
    ),
    "sa_zatca_simplified_invoice.xml": ExpectedInvoice(
        XmlInvoiceFormat.UBL,
        ExpectedOrigin("SA", "ZATCA"),
        "SA",
        payee_country="SA",
        tax_id="311111111101113",
        amount=Decimal("231.15"),
        currency="SAR",
    ),
    "de_xrechnung_ubl.xml": ExpectedInvoice(
        XmlInvoiceFormat.UBL,
        ExpectedOrigin("DE", "KoSIT"),
        "DE",
        payee_country="DE",
        tax_id="DE 123456789",
        amount=Decimal("336.9"),
        currency="EUR",
    ),
    "de_xrechnung_cii.xml": ExpectedInvoice(
        XmlInvoiceFormat.CII,
        ExpectedOrigin("DE", "KoSIT"),
        "DE",
        payee_country="DE",
        tax_id="DE 123456789",
        amount=Decimal("336.9"),
        currency="EUR",
    ),
    "eu_peppol_bis3_invoice.xml": ExpectedInvoice(
        XmlInvoiceFormat.UBL,
        None,
        None,
        payee_country="GB",
        payee_name="SupplierOfficialName Ltd",
        tax_id="GB1232434",
        amount=Decimal("1656.25"),
        currency="EUR",
    ),
    "eu_en16931_cii.xml": ExpectedInvoice(
        XmlInvoiceFormat.CII,
        None,
        None,
        payee_country="NL",
        payee_name="De Koksmaat",
        tax_id="NL8200.98.395.B.01",
        amount=Decimal("250.33"),
        currency="EUR",
    ),
}
PLACEHOLDER_TAX_ID_FIXTURES = frozenset({"pe_sunat_factura_ubl21.xml"})
EXPECTED_FIELD_NAMES = ("payee_name", "tax_id", "amount", "currency", "payee_country")


def test_every_official_fixture_has_an_expectation() -> None:
    fixture_names = {path.name for path in OFFICIAL_FIXTURES_DIR.glob("*.xml")}

    assert fixture_names == set(OFFICIAL_INVOICES)


@pytest.mark.parametrize(
    ("fixture_name", "expected"), list(OFFICIAL_INVOICES.items()), ids=list(OFFICIAL_INVOICES)
)
def test_official_invoice_origin_and_fields(fixture_name: str, expected: ExpectedInvoice) -> None:
    parsed = parse_invoice_xml((OFFICIAL_FIXTURES_DIR / fixture_name).read_bytes())

    assert parsed is not None
    assert parsed.format is expected.invoice_format
    assert parsed.fields.issuer_tax_country == expected.issuer_tax_country
    if expected.origin is None:
        assert parsed.origin is None
    else:
        assert parsed.origin is not None
        assert parsed.origin.country == expected.origin.country
        assert parsed.origin.authority == expected.origin.authority
        assert parsed.origin.issued_by is expected.origin.issued_by
    for field_name in EXPECTED_FIELD_NAMES:
        expected_value = getattr(expected, field_name)
        if expected_value is not None:
            assert getattr(parsed.fields, field_name) == expected_value, field_name


@pytest.mark.parametrize(
    "fixture_name",
    [name for name, expected in OFFICIAL_INVOICES.items() if expected.invoice_format is UNKNOWN],
)
def test_unmapped_national_formats_fall_back_to_the_language_model(fixture_name: str) -> None:
    parsed = parse_invoice_xml((OFFICIAL_FIXTURES_DIR / fixture_name).read_bytes())

    assert parsed is not None
    assert not parsed.fields.is_sufficient


@pytest.mark.parametrize(
    "fixture_name",
    [
        name
        for name, expected in OFFICIAL_INVOICES.items()
        if expected.tax_id
        and expected.issuer_tax_country
        and name not in PLACEHOLDER_TAX_ID_FIXTURES
    ],
)
def test_official_seller_tax_ids_fit_their_standard_country(fixture_name: str) -> None:
    expected = OFFICIAL_INVOICES[fixture_name]

    assert tax_id_fits_country(expected.tax_id, expected.issuer_tax_country) is not False


def test_placeholder_ruc_in_sunat_sample_is_flagged() -> None:
    expected = OFFICIAL_INVOICES["pe_sunat_factura_ubl21.xml"]

    assert tax_id_fits_country(expected.tax_id, expected.issuer_tax_country) is False
