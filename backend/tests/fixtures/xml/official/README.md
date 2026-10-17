# Official e-invoice XML fixtures

Real sample documents published by tax authorities, standards bodies, certified
providers or well-known open-source projects. They back
`tests/test_official_xml_fixtures.py`. Every file had its XML digital signatures
(`ds:Signature`, `xd:Signature`, bare xmldsig `Signature`) removed; nothing else was
changed unless the "Changes" column says so.

| Fixture | Standard | Source | Kind | Changes |
|---|---|---|---|---|
| `mx_cfdi40_ingreso.xml` | CFDI 4.0 (SAT) | github.com/MisaelMa/node-cfdi `packages/files/xml/examples/cfdi40/gobl.cfdi-invoice-b2c.xml` | Third-party, SAT test RFC | — |
| `mx_cfdi40_exportacion.xml` | CFDI 4.0 (SAT) | same repo, `gobl.cfdi-invoice-export.xml` | Third-party | — |
| `mx_cfdi33_ingreso.xml` | CFDI 3.3 (SAT) | github.com/phpcfdi/cfdi-to-json `tests/_files/cfdi-example.xml` | Third-party, stamped sample | — |
| `cl_dte33_envio_sii.xml` | DTE 33 (SII) | sii.cl `factura_electronica/factura_mercado/ejemplo_xml.zip` (`F60T33-ejemplo.xml`) | **Official** | — |
| `cl_dte46_factura_compra.xml` | DTE 46 (SII) | Derived from the official F60T33 sample | Derived | TipoDTE 33→46, receiver renamed as the seller, IVA retention added (SII guide: the buyer issues type 46; the seller is the Receptor). No official type 46 sample was found. |
| `co_dian_attached_document.xml` | DIAN AttachedDocument + Invoice UBL 2.1 | github.com/softeasyweb1966-web/LABORATORIO `zerbit/dian_FZ161.xml` | Real production document | **Anonymized**: party names, NITs, contact person, e-mails, phones and street addresses replaced with placeholders (DIAN's own NIT kept). |
| `co_dian_documento_soporte.xml` | DIAN documento soporte (InvoiceTypeCode 05) | github.com/agavariat/ver_xml `ds0901228066002200000001.xml` | DIAN habilitación test set (SETP) | — |
| `pe_sunat_factura_ubl21.xml` | SUNAT UBL 2.1 | github.com/project-openubl/xhandler-java `examples/xsender/src/main/resources/invoice.xml` | Third-party, placeholder RUC | — |
| `ec_sri_factura.xml` | SRI factura | github.com/miguelangarano/open-factura `src/example/invoice.xml` | Third-party, placeholder values | — |
| `ec_sri_liquidacion_compra.xml` | SRI liquidación de compra | github.com/junta-agua-uta/ja-facturacion-back `liquidacion-compra-ejemplo.xml` | Third-party test values | — |
| `br_nfe_nfeproc.xml` | NF-e 4.00 (SEFAZ) | github.com/nfephp-org/sped-nfe `tests/fixtures/xml/nfe_layout4_com_prot.xml` | Homologação (tpAmb=2) | — |
| `br_nfse_abrasf.xml` | NFS-e ABRASF 2.04 | github.com/jcamelosti/abrasf2-04-df `xml_exemplo_baseados_xsd/CompNfse.xml` | Third-party, XSD-based | — |
| `uy_cfe_envio.xml` | CFE (DGI) | efactura.dgi.gub.uy "Ejemplo de Sobre - Factura Cuenta Ajena con complemento fiscal NO encriptado" | **Official** | X509 certificate content replaced. |
| `cr_factura_electronica_44.xml` | Factura Electrónica 4.4 (Hacienda) | github.com/gaba95/PokeApiMVC `Factura.xml` | Third-party test data | — |
| `gt_fel_factura.xml` | FEL (SAT) | github.com/IT-Megaprint/Ejemplos-XML-v.2.0 `FACTURA.xml` | Certifier (Megaprint) example | — |
| `py_sifen_factura.xml` | SIFEN v150 (SET) | github.com/roshkadev/rshk-jsifenlib `docs/set/20190910_XSD_v150/XML v150/FE_v150_20190910.xml` | SET example package (mirror) | — |
| `do_ecf_consumo.xml` | e-CF 32 (DGII) | github.com/NetVux/e-CF-Doc `XMLs/132347986E320000000001.xml` | Third-party test data | — |
| `bo_siat_compra_venta.xml` | SIAT compra-venta (SIN) | github.com/albertoinch/Saleh-Gds-Electronica `xml/facturaElectronicaCompraVenta.xml` | Third-party | — |
| `it_fatturapa_fpr12.xml` | FatturaPA FPR12 v1.2 | fatturapa.gov.it `export/documenti/fatturapa/v1.2/IT01234567890_FPR01.xml` | **Official** | — |
| `es_facturae_31.xml` | Facturae 3.1 | facturae.gob.es `versiones-anteriores/a)-versión-3-1/factura_ejemplo_31.xml` | **Official** (no 3.2.2 sample published) | — |
| `pl_ksef_fa3.xml` | KSeF FA(3) | github.com/CIRFMF/ksef-pdf-generator `assets/invoice.xml` | **Official** (Ministry of Finance IT centre) | — |
| `gr_mydata_invoices_doc.xml` | myDATA InvoicesDoc (AADE) | github.com/netleyazilim/Developer `Electronic/Europe/Greece/myDATA/gr.myData.invoiceDoc.sample01.xml` | Third-party | — |
| `hu_nav_invoice_data.xml` | NAV Online Számla 3.0 | github.com/nav-gov-hu/Online-Invoice `sample/Data sample/Belfoldi termekertekesites.xml` | **Official** (NAV) | — |
| `tr_ubltr_temel_fatura.xml` | UBL-TR 1.2 TEMELFATURA | ebelge.gib.gov.tr `UBL-TR1.2.1_Paketi.zip` → `xml/TemelFaturaOrnegi.xml` | **Official** (GİB) | — |
| `tr_ubltr_ticari_fatura.xml` | UBL-TR 1.2 TICARIFATURA | same package, `xml/TicariFaturaOrnegi.xml` | **Official** (GİB) | — |
| `sa_zatca_standard_invoice.xml` | ZATCA FATOORA (standard) | github.com/mrsool/zatca `einvoicing-sdk/Data/Samples/Standard/Invoice/Standard_Invoice.xml` | ZATCA SDK sample (mirror) | — |
| `sa_zatca_simplified_invoice.xml` | ZATCA FATOORA (simplified) | same mirror, `Samples/Simplified/Invoice/Simplified_Invoice.xml` | ZATCA SDK sample (mirror) | — |
| `de_xrechnung_ubl.xml` | XRechnung 3.0 UBL | github.com/itplr-kosit/xrechnung-testsuite `src/test/business-cases/standard/01.01a-INVOICE_ubl.xml` | **Official** (KoSIT) | — |
| `de_xrechnung_cii.xml` | XRechnung 3.0 CII | same repo, `01.01a-INVOICE_uncefact.xml` | **Official** (KoSIT) | — |
| `eu_peppol_bis3_invoice.xml` | Peppol BIS Billing 3.0 | github.com/OpenPEPPOL/peppol-bis-invoice-3 `rules/examples/base-example.xml` | **Official** (OpenPeppol) | — |
| `eu_en16931_cii.xml` | EN 16931 CII | github.com/ConnectingEurope/eInvoicing-EN16931 `cii/examples/CII_example1.xml` | **Official** (European Commission) | — |

Not covered: Panamá (DGI portal unreachable, no public sample found) and Portugal
SAF-T PT (no sample published on the AT pages). Retrieved 2026-10-17.
