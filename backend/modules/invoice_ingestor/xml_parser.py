import re
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from xml.etree.ElementTree import Element

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring, iterparse

from contracts.payment_candidates import (
    DocumentFields,
    DocumentIssuer,
    DocumentOrigin,
    FieldEvidence,
    ParsedXmlInvoice,
    XmlInvoiceFormat,
)
from modules.invoice_ingestor.origin_registry import (
    CII_GUIDELINE_CONTEXT,
    DIAN_SUPPORT_DOCUMENT_MARKER,
    DIAN_SUPPORT_DOCUMENT_TYPE_CODES,
    DTE_BUYER_ISSUED_TYPES,
    EMBEDDED_DOCUMENT_ELEMENTS,
    NAMESPACE_AUTHORITY_ORIGINS,
    PROFILE_MARKER_ELEMENTS,
    PROFILE_MARKER_ORIGINS,
    SRI_BUYER_ISSUED_ROOTS,
    STRUCTURE_FINGERPRINTS,
    XmlOrigin,
)

DETERMINISTIC_CONFIDENCE = 1.0
ISO_DATE_LENGTH = 10
CII_DATE_FORMAT = "%Y%m%d"
DAY_FIRST_DATE_FORMAT = "%d/%m/%Y"
ISO_CURRENCY_LENGTH = 3
ISO_COUNTRY_LENGTH = 2

CFDI_NAMESPACE_PREFIX = "http://www.sat.gob.mx/cfd/"
DTE_NAMESPACE = "http://www.sii.cl/SiiDte"
UBL_INVOICE_NAMESPACE = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
CII_NAMESPACE_PREFIX = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice"
DTE_ROOT_NAMES = frozenset({"DTE", "Documento", "EnvioDTE"})

CHILEAN_PESO = "CLP"
DTE_BILL_TYPES = frozenset({"33", "34", "43", "46"})
SRI_ROOT_NAMES = frozenset({"factura", "liquidacionCompra"})
SRI_CURRENCY_NAMES = {"DOLAR": "USD", "DÓLAR": "USD"}
CFDI_INCOME_TYPE = "I"
CII_INVOICE_TYPE_CODES = frozenset({"380", "383", "386"})
DTE_CURRENCY_NAMES = {"PESO CL": "CLP", "DOLAR USA": "USD", "EURO": "EUR"}
NAMESPACE_DOMAIN_CONFIDENCE = 0.8
XML_DECLARATION = re.compile(r"^\s*<\?xml[^>]*\?>")
NATIONAL_SECOND_LEVEL_DOMAINS = frozenset({"gob", "gov", "gub", "org", "com", "net"})
NATIONAL_DOMAIN_MIN_LABELS = 3
NAMESPACE_HOST = re.compile(r"^(?:https?://)?(?P<host>[^/:]+)")
GENERIC_CURRENCY_ATTRIBUTES = ("currencyID", "currency", "Currency", "Moneda", "currencyCode")
GENERIC_CURRENCY_ELEMENTS = frozenset(
    {"DocumentCurrencyCode", "InvoiceCurrencyCode", "CurrencyCode", "Currency", "Moneda", "Divisa"}
)
GENERIC_TAX_ID_ELEMENTS = frozenset(
    {"Rfc", "RUT", "RUTEmisor", "NIT", "RUC", "CUIT", "CNPJ", "TaxID", "TaxId", "VATNumber"}
)


def parse_invoice_xml(xml_content: bytes) -> ParsedXmlInvoice | None:
    try:
        root = fromstring(xml_content)
    except (ParseError, DefusedXmlException):
        return None
    declared_namespaces = _declared_namespaces(xml_content)
    embedded_document = _embedded_document(root)
    invoice_root, invoice_namespaces = embedded_document or (root, declared_namespaces)
    origin = _with_issuer_role(
        invoice_root,
        detect_origin(invoice_root, invoice_namespaces) or detect_origin(root, declared_namespaces),
    )
    invoice_format = detect_format(invoice_root)
    fields = FORMAT_MAPPERS[invoice_format](invoice_root)
    if fields is None:
        return None
    if origin is not None:
        fields = _with_origin_country(fields, origin)
    return ParsedXmlInvoice(format=invoice_format, fields=fields, origin=origin)


def detect_origin(
    root: Element, declared_namespaces: list[str] | None = None
) -> DocumentOrigin | None:
    return (
        _namespace_authority_origin(root, declared_namespaces or [])
        or _structure_origin(root)
        or _profile_marker_origin(root)
    )


def detect_format(root: Element) -> XmlInvoiceFormat:
    namespace = _namespace(root.tag)
    local_name = _local_name(root.tag)
    if namespace.startswith(CFDI_NAMESPACE_PREFIX) and local_name == "Comprobante":
        return XmlInvoiceFormat.CFDI_MX
    if namespace == DTE_NAMESPACE and local_name in DTE_ROOT_NAMES:
        return XmlInvoiceFormat.DTE_CL
    if namespace == UBL_INVOICE_NAMESPACE and local_name == "Invoice":
        return XmlInvoiceFormat.UBL
    if namespace.startswith(CII_NAMESPACE_PREFIX):
        return XmlInvoiceFormat.CII
    if local_name in SRI_ROOT_NAMES and _child(root, "infoTributaria") is not None:
        return XmlInvoiceFormat.SRI_EC
    return XmlInvoiceFormat.UNKNOWN


def _map_cfdi(root: Element) -> DocumentFields | None:
    voucher_type = root.get("TipoDeComprobante")
    if voucher_type is not None and voucher_type != CFDI_INCOME_TYPE:
        return None
    issuer = _child(root, "Emisor")
    fiscal_stamp = _descendant(root, "TimbreFiscalDigital")
    series_and_folio = "-".join(part for part in (root.get("Serie"), root.get("Folio")) if part)
    collector = _FieldCollector()
    return DocumentFields(
        payee_name=collector.text("payee_name", _attribute(issuer, "Nombre")),
        tax_id=collector.text("tax_id", _attribute(issuer, "Rfc")),
        amount=collector.amount("amount", root.get("Total")),
        currency=collector.currency("currency", root.get("Moneda")),
        invoice_number=collector.text(
            "invoice_number", series_and_folio or _attribute(fiscal_stamp, "UUID")
        ),
        issue_date=collector.iso_date("issue_date", root.get("Fecha")),
        evidence=collector.evidence,
    )


def _map_dte(root: Element) -> DocumentFields | None:
    document = root if _local_name(root.tag) == "Documento" else _descendant(root, "Documento")
    header = _child(document, "Encabezado")
    document_id = _child(header, "IdDoc")
    issuer = _child(header, "Emisor")
    totals = _child(header, "Totales")
    document_type = _text(_child(document_id, "TipoDTE"))
    if document_type not in DTE_BILL_TYPES:
        return None
    collector = _FieldCollector()
    folio = _text(_child(document_id, "Folio"))
    is_buyer_issued = document_type in DTE_BUYER_ISSUED_TYPES
    seller = _child(header, "Receptor") if is_buyer_issued else issuer
    seller_name_element, seller_tax_id_element = (
        ("RznSocRecep", "RUTRecep") if is_buyer_issued else ("RznSoc", "RUTEmisor")
    )
    return DocumentFields(
        payee_name=collector.text("payee_name", _text(_child(seller, seller_name_element))),
        tax_id=collector.text("tax_id", _text(_child(seller, seller_tax_id_element))),
        amount=collector.amount("amount", _text(_child(totals, "MntTotal"))),
        currency=_dte_currency(collector, _text(_child(totals, "TpoMoneda")), document_type),
        invoice_number=collector.text(
            "invoice_number", f"{document_type}-{folio}" if folio else None
        ),
        issue_date=collector.iso_date("issue_date", _text(_child(document_id, "FchEmis"))),
        due_date=collector.iso_date("due_date", _text(_child(document_id, "FchVenc"))),
        evidence=collector.evidence,
    )


def _map_ubl(root: Element) -> DocumentFields:
    supplier = _path(root, "AccountingSupplierParty", "Party")
    legal_entity = _child(supplier, "PartyLegalEntity")
    payable_amount = _path(root, "LegalMonetaryTotal", "PayableAmount")
    supplier_country = _text(_child(_descendant(supplier, "Country"), "IdentificationCode"))
    supplier_name = (
        _text(_child(legal_entity, "RegistrationName"))
        or _text(_path(supplier, "PartyTaxScheme", "RegistrationName"))
        or _text(_path(supplier, "PartyName", "Name"))
    )
    supplier_tax_id = _text(_descendant(supplier, "CompanyID")) or _text(
        _path(supplier, "PartyIdentification", "ID")
    )
    collector = _FieldCollector()
    return DocumentFields(
        payee_name=collector.text("payee_name", supplier_name),
        tax_id=collector.text("tax_id", supplier_tax_id),
        amount=collector.amount("amount", _text(payable_amount)),
        currency=collector.currency(
            "currency",
            _text(_child(root, "DocumentCurrencyCode")) or _attribute(payable_amount, "currencyID"),
        ),
        payee_country=collector.country("payee_country", supplier_country),
        invoice_number=collector.text("invoice_number", _text(_child(root, "ID"))),
        issue_date=collector.iso_date("issue_date", _text(_child(root, "IssueDate"))),
        due_date=collector.iso_date("due_date", _text(_child(root, "DueDate"))),
        evidence=collector.evidence,
    )


def _map_cii(root: Element) -> DocumentFields | None:
    document = _child(root, "ExchangedDocument")
    type_code = _text(_child(document, "TypeCode"))
    if type_code is not None and type_code not in CII_INVOICE_TYPE_CODES:
        return None
    transaction = _child(root, "SupplyChainTradeTransaction")
    seller = _path(transaction, "ApplicableHeaderTradeAgreement", "SellerTradeParty")
    settlement = _child(transaction, "ApplicableHeaderTradeSettlement")
    summation = _child(settlement, "SpecifiedTradeSettlementHeaderMonetarySummation")
    grand_total = _first_present(
        _child(summation, "DuePayableAmount"), _child(summation, "GrandTotalAmount")
    )
    seller_tax_id = _text(_path(seller, "SpecifiedTaxRegistration", "ID")) or _text(
        _path(seller, "SpecifiedLegalOrganization", "ID")
    )
    collector = _FieldCollector()
    return DocumentFields(
        payee_name=collector.text("payee_name", _text(_child(seller, "Name"))),
        tax_id=collector.text("tax_id", seller_tax_id),
        amount=collector.amount("amount", _text(grand_total)),
        currency=collector.currency(
            "currency",
            _text(_child(settlement, "InvoiceCurrencyCode"))
            or _attribute(grand_total, "currencyID"),
        ),
        payee_country=collector.country(
            "payee_country", _text(_path(seller, "PostalTradeAddress", "CountryID"))
        ),
        invoice_number=collector.text("invoice_number", _text(_child(document, "ID"))),
        issue_date=collector.compact_date(
            "issue_date", _text(_path(document, "IssueDateTime", "DateTimeString"))
        ),
        due_date=collector.compact_date(
            "due_date",
            _text(
                _path(
                    settlement,
                    "SpecifiedTradePaymentTerms",
                    "DueDateDateTime",
                    "DateTimeString",
                )
            ),
        ),
        evidence=collector.evidence,
    )


def _map_sri(root: Element) -> DocumentFields:
    tax_info = _child(root, "infoTributaria")
    is_purchase_settlement = _local_name(root.tag) in SRI_BUYER_ISSUED_ROOTS
    document_info = _child(
        root, "infoLiquidacionCompra" if is_purchase_settlement else "infoFactura"
    )
    payee_block, payee_name_element, payee_tax_id_element = (
        (document_info, "razonSocialProveedor", "identificacionProveedor")
        if is_purchase_settlement
        else (tax_info, "razonSocial", "ruc")
    )
    document_number = "-".join(
        part
        for part in (
            _text(_child(tax_info, "estab")),
            _text(_child(tax_info, "ptoEmi")),
            _text(_child(tax_info, "secuencial")),
        )
        if part
    )
    raw_currency = _text(_child(document_info, "moneda"))
    collector = _FieldCollector()
    return DocumentFields(
        payee_name=collector.text("payee_name", _text(_child(payee_block, payee_name_element))),
        tax_id=collector.text("tax_id", _text(_child(payee_block, payee_tax_id_element))),
        amount=collector.amount("amount", _text(_child(document_info, "importeTotal"))),
        currency=collector.currency(
            "currency", SRI_CURRENCY_NAMES.get((raw_currency or "").upper(), raw_currency)
        ),
        invoice_number=collector.text("invoice_number", document_number or None),
        issue_date=collector.day_first_date(
            "issue_date", _text(_child(document_info, "fechaEmision"))
        ),
        evidence=collector.evidence,
    )


def _map_unknown(root: Element) -> DocumentFields:
    collector = _FieldCollector()
    return DocumentFields(
        tax_id=collector.text("tax_id", _first_descendant_text(root, GENERIC_TAX_ID_ELEMENTS)),
        currency=collector.currency("currency", _generic_currency(root)),
        issuer_tax_country=collector.country(
            "issuer_tax_country",
            _namespace_country(_namespace(root.tag)),
            NAMESPACE_DOMAIN_CONFIDENCE,
        ),
        evidence=collector.evidence,
    )


FORMAT_MAPPERS: dict[XmlInvoiceFormat, Callable[[Element], DocumentFields | None]] = {
    XmlInvoiceFormat.CFDI_MX: _map_cfdi,
    XmlInvoiceFormat.DTE_CL: _map_dte,
    XmlInvoiceFormat.UBL: _map_ubl,
    XmlInvoiceFormat.CII: _map_cii,
    XmlInvoiceFormat.SRI_EC: _map_sri,
    XmlInvoiceFormat.UNKNOWN: _map_unknown,
}


class _FieldCollector:
    def __init__(self) -> None:
        self.evidence: list[FieldEvidence] = []

    def text(self, field: str, raw_value: str | None) -> str | None:
        if not raw_value:
            return None
        self._record(field, raw_value)
        return raw_value

    def amount(self, field: str, raw_value: str | None) -> Decimal | None:
        if not raw_value:
            return None
        try:
            parsed_amount = Decimal(raw_value)
        except InvalidOperation:
            return None
        self._record(field, raw_value)
        return parsed_amount

    def currency(self, field: str, raw_value: str | None) -> str | None:
        normalized_currency = (raw_value or "").strip().upper()
        if len(normalized_currency) != ISO_CURRENCY_LENGTH:
            return None
        self._record(field, raw_value or normalized_currency)
        return normalized_currency

    def country(
        self, field: str, raw_value: str | None, confidence: float = DETERMINISTIC_CONFIDENCE
    ) -> str | None:
        normalized_country = (raw_value or "").strip().upper()
        if len(normalized_country) != ISO_COUNTRY_LENGTH:
            return None
        self._record(field, raw_value or normalized_country, confidence)
        return normalized_country

    def day_first_date(self, field: str, raw_value: str | None) -> date | None:
        if not raw_value:
            return None
        try:
            parsed_date = datetime.strptime(raw_value, DAY_FIRST_DATE_FORMAT).date()
        except ValueError:
            return None
        self._record(field, raw_value)
        return parsed_date

    def implied(self, field: str, standard_value: str, standard_quote: str) -> str:
        self._record(field, standard_quote)
        return standard_value

    def iso_date(self, field: str, raw_value: str | None) -> date | None:
        if not raw_value:
            return None
        try:
            parsed_date = date.fromisoformat(raw_value[:ISO_DATE_LENGTH])
        except ValueError:
            return None
        self._record(field, raw_value)
        return parsed_date

    def compact_date(self, field: str, raw_value: str | None) -> date | None:
        if not raw_value:
            return None
        try:
            parsed_date = datetime.strptime(raw_value, CII_DATE_FORMAT).date()
        except ValueError:
            return self.iso_date(field, raw_value)
        self._record(field, raw_value)
        return parsed_date

    def _record(self, field: str, quote: str, confidence: float = DETERMINISTIC_CONFIDENCE) -> None:
        self.evidence.append(FieldEvidence(field=field, quote=quote, confidence=confidence))


def _dte_currency(collector: _FieldCollector, raw_currency: str | None, document_type: str) -> str:
    named_currency = DTE_CURRENCY_NAMES.get((raw_currency or "").strip().upper())
    explicit_currency = collector.currency("currency", named_currency or raw_currency)
    if explicit_currency is not None:
        return explicit_currency
    standard_quote = f"TipoDTE {document_type} without TpoMoneda: amounts in CLP (SII standard)"
    return collector.implied("currency", CHILEAN_PESO, standard_quote)


def _namespace_authority_origin(
    root: Element, declared_namespaces: list[str]
) -> DocumentOrigin | None:
    element_namespaces = [_namespace(node.tag) for node in root.iter()]
    for namespace in dict.fromkeys([*element_namespaces, *declared_namespaces]):
        lowered_namespace = namespace.lower()
        for authority_token, origin in NAMESPACE_AUTHORITY_ORIGINS.items():
            if authority_token in lowered_namespace:
                return _document_origin(origin, namespace)
    return None


def _structure_origin(root: Element) -> DocumentOrigin | None:
    root_name = _local_name(root.tag)
    for fingerprint in STRUCTURE_FINGERPRINTS:
        has_fingerprint = (
            root_name in fingerprint.root_names
            and _child(root, fingerprint.required_child) is not None
        )
        if has_fingerprint:
            return _document_origin(
                fingerprint.origin, f"<{root_name}><{fingerprint.required_child}>"
            )
    return None


def _profile_marker_origin(root: Element) -> DocumentOrigin | None:
    for profile_text in _profile_texts(root):
        upper_profile = profile_text.upper()
        for marker, origin in PROFILE_MARKER_ORIGINS.items():
            if marker in upper_profile:
                return _document_origin(origin, profile_text)
    return None


def _profile_texts(root: Element) -> list[str]:
    profile_elements = [_child(root, name) for name in PROFILE_MARKER_ELEMENTS]
    guideline = _descendant(root, CII_GUIDELINE_CONTEXT)
    profile_elements.append(_child(guideline, "ID"))
    return [
        " ".join([element.text or "", *element.attrib.values()]).strip()
        for element in profile_elements
        if element is not None
    ]


def _document_origin(origin: XmlOrigin, signal: str) -> DocumentOrigin:
    return DocumentOrigin(
        country=origin.country,
        standard=origin.standard,
        authority=origin.authority,
        signal=signal,
    )


def _with_origin_country(fields: DocumentFields, origin: DocumentOrigin) -> DocumentFields:
    other_evidence = [
        evidence for evidence in fields.evidence if evidence.field != "issuer_tax_country"
    ]
    if origin.issued_by is DocumentIssuer.BUYER:
        return fields.model_copy(update={"issuer_tax_country": None, "evidence": other_evidence})
    origin_evidence = FieldEvidence(
        field="issuer_tax_country", quote=origin.signal, confidence=DETERMINISTIC_CONFIDENCE
    )
    return fields.model_copy(
        update={
            "issuer_tax_country": origin.country,
            "evidence": [origin_evidence, *other_evidence],
        }
    )


def _with_issuer_role(root: Element, origin: DocumentOrigin | None) -> DocumentOrigin | None:
    if origin is None:
        return None
    buyer_issued_signal = _buyer_issued_signal(root)
    if buyer_issued_signal is None:
        return origin
    return origin.model_copy(
        update={
            "issued_by": DocumentIssuer.BUYER,
            "signal": f"{origin.signal} | {buyer_issued_signal}",
        }
    )


def _buyer_issued_signal(root: Element) -> str | None:
    root_name = _local_name(root.tag)
    if root_name in SRI_BUYER_ISSUED_ROOTS:
        return f"<{root_name}>"
    dte_type = _text(_descendant(root, "TipoDTE"))
    if dte_type in DTE_BUYER_ISSUED_TYPES:
        return f"TipoDTE {dte_type}"
    support_document_profile = next(
        (
            profile_text
            for profile_text in _profile_texts(root)
            if DIAN_SUPPORT_DOCUMENT_MARKER in profile_text.upper()
        ),
        None,
    )
    if support_document_profile is not None:
        return support_document_profile
    invoice_type_code = _text(_child(root, "InvoiceTypeCode"))
    is_dian_support_document = invoice_type_code in DIAN_SUPPORT_DOCUMENT_TYPE_CODES and any(
        "dian" in _namespace(node.tag).lower() for node in root.iter()
    )
    return f"InvoiceTypeCode {invoice_type_code}" if is_dian_support_document else None


def _embedded_document(root: Element) -> tuple[Element, list[str]] | None:
    for node in root.iter():
        is_embedding_element = node is not root and _local_name(node.tag) in (
            EMBEDDED_DOCUMENT_ELEMENTS
        )
        embedded_text = (node.text or "").strip() if is_embedding_element else ""
        if not embedded_text.startswith("<"):
            continue
        embedded_content = XML_DECLARATION.sub("", embedded_text, count=1).encode()
        try:
            return fromstring(embedded_content), _declared_namespaces(embedded_content)
        except (ParseError, DefusedXmlException):
            continue
    return None


def _declared_namespaces(xml_content: bytes) -> list[str]:
    try:
        return [
            namespace_uri
            for _, (_, namespace_uri) in iterparse(BytesIO(xml_content), events=("start-ns",))
        ]
    except (ParseError, DefusedXmlException):
        return []


def _generic_currency(root: Element) -> str | None:
    for node in root.iter():
        attribute_currency = next(
            (node.get(name) for name in GENERIC_CURRENCY_ATTRIBUTES if node.get(name)), None
        )
        if attribute_currency:
            return attribute_currency
        if _local_name(node.tag) in GENERIC_CURRENCY_ELEMENTS and _text(node):
            return _text(node)
    return None


def _first_descendant_text(root: Element, local_names: frozenset[str]) -> str | None:
    return next(
        (
            _text(node)
            for node in root.iter()
            if _local_name(node.tag) in local_names and _text(node)
        ),
        None,
    )


def _namespace_country(namespace: str) -> str | None:
    host_match = NAMESPACE_HOST.match(namespace)
    if host_match is None:
        return None
    host_labels = host_match.group("host").lower().split(".")
    is_national_domain = (
        len(host_labels) >= NATIONAL_DOMAIN_MIN_LABELS
        and len(host_labels[-1]) == ISO_COUNTRY_LENGTH
        and host_labels[-2] in NATIONAL_SECOND_LEVEL_DOMAINS
    )
    return host_labels[-1].upper() if is_national_domain else None


def _namespace(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(element: Element | None, local_name: str) -> Element | None:
    if element is None:
        return None
    return next((child for child in element if _local_name(child.tag) == local_name), None)


def _path(element: Element | None, *local_names: str) -> Element | None:
    current = element
    for local_name in local_names:
        current = _child(current, local_name)
    return current


def _descendant(element: Element | None, local_name: str) -> Element | None:
    if element is None:
        return None
    return next((node for node in element.iter() if _local_name(node.tag) == local_name), None)


def _first_present(*elements: Element | None) -> Element | None:
    return next((element for element in elements if element is not None), None)


def _text(element: Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    return element.text.strip() or None


def _attribute(element: Element | None, name: str) -> str | None:
    if element is None:
        return None
    return (element.get(name) or "").strip() or None
