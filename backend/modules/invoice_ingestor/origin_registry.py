from dataclasses import dataclass


@dataclass(frozen=True)
class XmlOrigin:
    country: str
    standard: str
    authority: str


@dataclass(frozen=True)
class XmlStructureFingerprint:
    root_names: frozenset[str]
    required_child: str
    origin: XmlOrigin


NAMESPACE_AUTHORITY_ORIGINS: dict[str, XmlOrigin] = {
    "sat.gob.mx": XmlOrigin("MX", "CFDI", "SAT"),
    "sii.cl": XmlOrigin("CL", "DTE", "SII"),
    "dian.gov.co": XmlOrigin("CO", "Factura electrónica UBL", "DIAN"),
    "dian:gov:co": XmlOrigin("CO", "Factura electrónica UBL", "DIAN"),
    "urn:sunat": XmlOrigin("PE", "CPE UBL", "SUNAT"),
    "sunat.gob.pe": XmlOrigin("PE", "CPE UBL", "SUNAT"),
    "portalfiscal.inf.br": XmlOrigin("BR", "NF-e", "SEFAZ"),
    "abrasf.org.br": XmlOrigin("BR", "NFS-e", "ABRASF"),
    "sped.fazenda.gov.br": XmlOrigin("BR", "NFS-e Nacional", "Receita Federal"),
    "dgi.gub.uy": XmlOrigin("UY", "CFE", "DGI"),
    "comprobanteselectronicos.go.cr": XmlOrigin("CR", "Comprobante electrónico", "Hacienda"),
    "hacienda.go.cr": XmlOrigin("CR", "Comprobante electrónico", "Hacienda"),
    "sat.gob.gt": XmlOrigin("GT", "FEL", "SAT"),
    "ekuatia.set.gov.py": XmlOrigin("PY", "SIFEN", "SET"),
    "mef.gob.pa": XmlOrigin("PA", "Factura electrónica", "DGI"),
    "dgii.gov.do": XmlOrigin("DO", "e-CF", "DGII"),
    "impuestos.gob.bo": XmlOrigin("BO", "Factura electrónica", "SIN"),
    "agenziaentrate.gov.it": XmlOrigin("IT", "FatturaPA", "Agenzia delle Entrate"),
    "fatturapa.gov.it": XmlOrigin("IT", "FatturaPA", "Agenzia delle Entrate"),
    "facturae.gob.es": XmlOrigin("ES", "Facturae", "AEAT"),
    "facturae.es/": XmlOrigin("ES", "Facturae", "AEAT"),
    "crd.gov.pl": XmlOrigin("PL", "KSeF FA", "Ministerstwo Finansów"),
    "nav.gov.hu": XmlOrigin("HU", "Online Számla", "NAV"),
    "aade.gr": XmlOrigin("GR", "myDATA", "AADE"),
    "standardauditfile-tax:pt": XmlOrigin("PT", "SAF-T PT", "AT"),
}

STRUCTURE_FINGERPRINTS: tuple[XmlStructureFingerprint, ...] = (
    XmlStructureFingerprint(
        frozenset(
            {
                "factura",
                "notaCredito",
                "notaDebito",
                "comprobanteRetencion",
                "liquidacionCompra",
                "guiaRemision",
            }
        ),
        "infoTributaria",
        XmlOrigin("EC", "Comprobante electrónico", "SRI"),
    ),
    XmlStructureFingerprint(frozenset({"ECF"}), "Encabezado", XmlOrigin("DO", "e-CF", "DGII")),
    XmlStructureFingerprint(frozenset({"GTDocumento"}), "SAT", XmlOrigin("GT", "FEL", "SAT")),
    XmlStructureFingerprint(
        frozenset(
            {
                "facturaElectronicaCompraVenta",
                "facturaComputarizadaCompraVenta",
                "facturaElectronicaServicioBasico",
                "facturaComputarizadaServicioBasico",
                "facturaElectronicaAlquilerBienInmueble",
                "facturaComputarizadaAlquilerBienInmueble",
            }
        ),
        "cabecera",
        XmlOrigin("BO", "Factura electrónica SIAT", "SIN"),
    ),
)

PROFILE_MARKER_ORIGINS: dict[str, XmlOrigin] = {
    "DIAN": XmlOrigin("CO", "Factura electrónica UBL", "DIAN"),
    "SUNAT": XmlOrigin("PE", "CPE UBL", "SUNAT"),
    "TR1.2": XmlOrigin("TR", "UBL-TR e-Fatura", "GİB"),
    "TEMELFATURA": XmlOrigin("TR", "UBL-TR e-Fatura", "GİB"),
    "TICARIFATURA": XmlOrigin("TR", "UBL-TR e-Fatura", "GİB"),
    "REPORTING:1.0": XmlOrigin("SA", "FATOORA UBL", "ZATCA"),
    "XRECHNUNG": XmlOrigin("DE", "XRechnung", "KoSIT"),
    "XEINKAUF.DE": XmlOrigin("DE", "XRechnung", "KoSIT"),
    "FATTURAPA.GOV.IT": XmlOrigin("IT", "CIUS-IT", "Agenzia delle Entrate"),
}

PROFILE_MARKER_ELEMENTS = frozenset({"CustomizationID", "ProfileID"})
CII_GUIDELINE_CONTEXT = "GuidelineSpecifiedDocumentContextParameter"
EMBEDDED_DOCUMENT_ELEMENTS = frozenset({"Description", "comprobante"})

DTE_BUYER_ISSUED_TYPES = frozenset({"46"})
SRI_BUYER_ISSUED_ROOTS = frozenset({"liquidacionCompra"})
DIAN_SUPPORT_DOCUMENT_MARKER = "DOCUMENTO SOPORTE"
DIAN_SUPPORT_DOCUMENT_TYPE_CODES = frozenset({"05"})
