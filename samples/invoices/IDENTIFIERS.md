# Identificadores en facturas, por tipo de emisor

Research de los identificadores que suelen aparecer en documentos de cobro, mapeados al
`IdentifierKind` del sistema (`contracts/payment_policy.py`: `tax_id`, `bank_account`,
`service_account_id`, `email`, `domain`, `alias`) y a qué PDF del set ejercita cada uno.

El orden de matching del diseño es: **tax_id → bank_account → service_account_id → email →
domain → nombre normalizado o alias**. Los matcheos por nombre parcial nunca se confían (R04).

## 1. Empresa de servicios / SaaS global (compañía)

| Identificador en el documento | IdentifierKind | Ejemplos reales | Caso PDF |
|---|---|---|---|
| Razón social legal completa | `alias` (nombre normalizado) | "ACME Cloud Inc." / "Acme Cloud Incorporated" | 01, 36 (variante long-form) |
| ID tributario del emisor | `tax_id` | **EIN** (US, IRS) `12-3456789` · **VAT ID** (UE) `DE812345678` · **RUT** (CL) `76.543.210-K` · **RFC** (MX) · **CUIT** (AR) · **NIT** (CO) · **CNPJ** (BR) · **RUC** (PE) | 01 (EIN), 05 (VAT), 04 (RUT), 24 (VKN turco) |
| Número de factura secuencial único | — (folio; parte de la huella dedup) | `INV-2048`, `RE-2026-114` | todos |
| ID de cuenta de servicio del cliente | `service_account_id` | "AWS account 1234-5678-9098", "GitHub org blinka-demo", "Customer ID C-88231" | 02 (org plan) |
| Email / dominio de facturación | `email` / `domain` | billing@acme-cloud.com, dominio acme-cloud.com | 01, 22 (dominio lookalike) |
| Cuenta bancaria de abono (remit-to) | `bank_account` | Routing+Account (US), IBAN (UE) | 21 (IBAN nuevo), 26 (cuenta desconocida), 05 |
| Método de pago declarado | — (atributo del payee: `card_on_file` vs `bank_transfer`) | "card on file VISA **** 4242" | 02 (tarjeta), 28 (pide transferencia siendo tarjeta) |
| Nº de orden de compra (PO) | — | PO-77821 | (informativo, sin regla) |

En la UE una factura con IVA exige por directiva (art. 226): número secuencial único, nombre y
dirección de emisor y cliente, VAT ID del proveedor (y del cliente en B2B), fecha de emisión.
En EE. UU. el EIN es el equivalente del VAT; el remit-to bancario es práctica de AP, no legal.

## 2. Persona natural / contratista (cuenta de cobro)

| Identificador en el documento | IdentifierKind | Notas | Caso PDF |
|---|---|---|---|
| Nombre completo de la persona | `alias` | "María Fernanda Rojas Díaz"; parcial ("María Rojas") NO se confía | 03, 37 (parcial) |
| ID tributario personal | `tax_id` | Mismo formato que empresas en cada país: RUT persona (CL), CC/NIT (CO), RFC persona física (MX), CUIT (AR) | 03, 42 |
| **Sin folio** — clave es período + vencimiento | — | La huella dedup usa `due:{fecha}` cuando no hay número | 03, 19, 34 |
| Cuenta bancaria personal | `bank_account` | El dato más fuerte contra suplantación | 03, 27 (cuenta de persona en factura de empresa → R05) |
| Email personal de contacto | `email` | maria.rojas@… | 37 |
| Monto acordado (fee mensual) | — (atributo `agreed_amount_usd` del payee) | R17 compara contra el acuerdo | 03 vs 13 |

La cuenta de cobro de persona es el documento más fácil de falsificar: sin folio fiscal, sin
firma, y el mismo nombre parcial puede corresponder a cualquiera. De ahí que R04 mande a review
los nombres parciales sin identificador fuerte.

## 3. Factura electrónica fiscal (DTE chileno y similares)

El SII define el formato DTE con (formato_dte, SII):

| Campo DTE | Equivalente en el sistema | Caso PDF |
|---|---|---|
| `TipoDTE` (33 factura, 34 exenta, 61 nota de crédito, 56 nota de débito…) | clasificación del documento: bill vs no-bill | 04 (33), 32 (nota de crédito → NO BILL) |
| `Folio` | número de factura (huella dedup) | 04, 41 |
| `RUT Emisor` / `RUT Receptor` | `tax_id` del payee / del owner | 04, 06, 07 |
| Fecha emisión / vencimiento | `due_date` (R01) | 33 (sin vencimiento), 50 (futura) |
| `FolioRef` (referencias en notas de crédito/débito) | vínculo con factura original | 32 (anula 5531) |
| IVA desglosado (19% CL, 21% AR, 16% CO, IVA UE) | neto vs total; regla CLP: total incluye IVA | 04, 07, 48 (IVA con centavos, inválido en CLP) |
| UF / UTM reajustables | moneda `CLF` | 06 |

Otros países: México CFDI (RFC + UUID/sello), Argentina (CAE de AFIP), Colombia (CUDE de DIAN).
El folio fiscal electrónico es autoritario: un folio reutilizado con otro monto (`18`) es señal
de manipulación.

## Matriz identificador → caso que lo estresa

| Identificador fuerte | Caso legítimo | Caso trampa |
|---|---|---|
| `tax_id` | 01, 04, 05 | 22 (EIN distinto con mismo nombre), 36 (alias long-form) |
| `bank_account` | 03, 05 | 21 (cambio de cuenta), 26 (cuenta desconocida), 27 (cuenta de persona en factura de empresa) |
| `service_account_id` | 02 | (futuro: factura que cita otra org) |
| `email`/`domain` | 01 | 22 (dominio lookalike `acme-cloud-support.co`), 40 (reenvío desde otra casilla) |
| `alias`/nombre | 01, 03 | 37 (nombre parcial), 12 (nombre no registrado) |
| folio | 04, 41 | 10 (dup exacto), 11 (fuzzy), 17 (mismo folio re-formateado), 18 (folio reutilizado con otro monto) |

## Fuentes

- SII Chile — [Formato Documentos Tributarios Electrónicos](https://www.sii.cl/factura_electronica/factura_mercado/formato_dte_202602.pdf) · [Instructivo emisión](https://www.sii.cl/factura_electronica/factura_mercado/instructivo_emision.pdf) · [Banco Central: DTE y FolioRef](https://www.bcentral.cl/documents/33528/112436/BCCh-Instructivo-Proveedores-Emision-Recepcion-Pago-DTE.pdf)
- Comisión Europea — requisitos de factura con IVA (Directiva art. 226, vía [Stripe](https://stripe.com) y [Irish Revenue](https://revenue.ie) resúmenes)
- LatAm personas naturales — [DIAN Colombia: NIT/RUT](https://guias.webempresa.com/preguntas-frecuentes/numero-identificacion-fiscal/) · [Facturama: RFC/CFDI México](https://facturama.com) · [Buenos Aires: CUIT/AFIP](https://buenosaires.gob.ar)
