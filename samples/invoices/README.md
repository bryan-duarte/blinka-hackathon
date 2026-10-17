# Facturas de prueba (PDF)

Set de 50 PDFs generados por `backend/scripts/generate_test_invoices.py` para probar el flujo de
email → inbox → guardrails → agente de pagos. Todos son PDFs con texto extraíble (pypdf) y el
script auto-verifica los marcadores de cada caso al generarlos.
Regenerar con: `cd backend && uv run python scripts/generate_test_invoices.py`.

Ver `IDENTIFIERS.md` para la taxonomía de identificadores por tipo de emisor y qué caso
estresa cada uno.

## Política de pago de la empresa ficticia (Blinka Demo Corp)

Para que los casos trampa tengan sentido, estos PDFs asumen esta configuración:

| Regla | Valor |
|---|---|
| Tope duro por pago (`hard_cap_per_payment_usd`) | USD 5.000 |
| Tope de autopago (`auto_pay_max_usd`) | USD 1.000 |
| Presupuesto mensual global | USD 20.000 |
| Presupuesto por categoría | cloud USD 3.000 · saas USD 1.500 · contractor USD 2.500 · prof. services USD 3.000 |
| Categorías permitidas | cloud, saas, contractor, professional_services, utilities, rent |
| Monedas permitidas | USD, CLP, EUR, CLF |
| Ventana de duplicados | 45 días |

**Beneficiarios registrados:**

| Payee | Tipo | Categoría | Identificadores registrados |
|---|---|---|---|
| ACME Cloud Inc. (alias: "Acme Cloud Incorporated") | company | cloud | EIN 12-3456789, billing@acme-cloud.com |
| GitHub, Inc. | company | saas | `card_on_file` VISA **** 4242 |
| María Fernanda Rojas Díaz | person | contractor | RUT 12.345.678-9, Banco de Chile CC 001-23456-90, acuerdo USD 1.500 ±5% |
| Carlos Andrés Pérez Silva | person | contractor | RUT 13.222.333-4, Santander CC 0-99887766 |
| Servicios Integrales del Sur SpA | company | professional_services | RUT 76.543.210-K, dte@proveedor.cl |
| Delta Consulting GmbH | company | professional_services | VAT DE812345678, IBAN DE89..., dominio delta-consulting.de |
| Administración Edificio Andino SpA | company | rent | cobra en UF |
| Compañía Eléctrica Andes S.A. | company | utilities | |
| Atlantis Analytics S.A. | company | saas | |

**Lista negra:** Omega Design Studio (RUT 77.900.100-3).
**No registrados:** Nova Tech Solutions LLC, Andes Marketing Group, Bosphorus Data Analytics,
Global Services Partners, Servicios Cloud Pacific S.A., Halo Domains LLC.

## Matriz de casos

### Normales → pagar (01–08)

| Archivo | Escenario |
|---|---|
| `01-cloud-acme-usd-normal.pdf` | USD 120, bajo todos los topes |
| `02-saas-github-usd-normal.pdf` | USD 250, tarjeta en archivo |
| `03-contractor-rojas-cuenta-clp.pdf` | Cuenta de cobro **sin nº de factura** (CLP 1.190.000 c/IVA); la huella usa el vencimiento |
| `04-services-sur-clp-iva.pdf` | Factura chilena: neto + IVA 19%, formato `$119.000` |
| `05-consulting-delta-eur.pdf` | EUR 2.400 ≈ USD 2.600, formato alemán (`2.400,00`) |
| `06-admin-uf-clf.pdf` | Cobre en UF (CLF 3,85) |
| `07-utilities-electricity-clp.pdf` | Suministro eléctrico CLP 342.770 |
| `08-saas-many-items-usd.pdf` | 15 ítems (estrés de extracción), total USD 893,40 |

### Duplicados y cobros repetidos al mismo payee (10–19, 40–43, 51)

| Archivo | Escenario | Veredicto esperado |
|---|---|---|
| `10-dup-exact-acme.pdf` | Bytes idénticos a 01 (reenvío del mismo PDF) | DUP |
| `11-dup-fuzzy-acme.pdf` | Mismo payee, otro folio, monto a +0,4% (120,50) | REVIEW R11 |
| `17-dup-reformatted-acme.pdf` | Mismos datos de 01 pero otra plantilla: hash distinto, **huella igual** | DUP |
| `18-dup-same-number-altered-amount.pdf` | Folio INV-2048 reutilizado con monto x10 | REVIEW (CHK3) |
| `19-dup-cuenta-resend-new-amount.pdf` | Cuenta de cobro reenviada, mismo vencimiento, +0,4% | REVIEW R11 |
| `40-dup-forwarded-sur.pdf` | Copia de 04 reenviada desde otra casilla | DUP (hash de documento) |
| `43-legit-subscription-same-amount.pdf` | Suscripción legítima, folio nuevo, **mismo monto** dentro de ventana 45d | REVIEW R11 (fricción por diseño) |
| `51-dup-cross-currency-acme.pdf` | El mismo servicio cobrado en CLP (≈ USD 120 al tipo 950) | REVIEW R11 (equivalente USD) |
| `41-legit-sur-5532.pdf` | Mismo proveedor que 04, folio y servicio distintos | **PAY** (no es duplicado) |
| `42-legit-second-contractor-same-amount.pdf` | Segundo contratista, total idéntico al de 03 | **PAY** (payee distinto) |

### Trampas del reto / CLAUDE.md (12–16)

| Archivo | Escenario | Veredicto esperado |
|---|---|---|
| `12-new-payee-nova.pdf` | Beneficiario nuevo no registrado | REVIEW R04 |
| `13-agreed-mismatch-rojas.pdf` | Contratista cobra USD 2.200 vs acuerdo USD 1.500 ±5% | REVIEW R17 |
| `14-over-hard-cap-acme.pdf` | USD 6.500 > tope duro 5.000 | HOLD R12 |
| `15-over-autopay-github.pdf` | USD 1.800 ≤ tope duro pero > autopago | REVIEW R13 |
| `16-budget-cloud-acme.pdf` | USD 2.950: rompe presupuesto cloud solo si antes se envió 01 (120 + 2.950 > 3.000) | HOLD R14 (secuencial) |
| `38-split-billing-sur-a.pdf` + `39-split-billing-b.pdf` | Fraccionamiento: dos facturas de USD 2.400 el mismo día para esquivar el tope | A: REVIEW R13 · B: HOLD R14 (2.400+2.400 > 3.000) |

### Fraude / identidad (20–29)

| Archivo | Escenario | Veredicto esperado |
|---|---|---|
| `20-blacklist-omega.pdf` | Payee en lista negra | HOLD R03 |
| `21-bank-change-delta.pdf` | Factura válida con "cambio de cuenta bancaria" embebido (BEC) | HOLD R02 |
| `22-impersonation-acme-lookalike.pdf` | Se hace pasar por ACME (EIN distinto, dominio `acme-cloud-support.co`, urgencia) | HOLD R05 |
| `26-identity-wrong-bank-acme.pdf` | ACME real (EIN correcto) pero pide transferir a una cuenta no registrada | HOLD R05 |
| `27-identity-person-bank-on-company-bill.pdf` | Factura de "empresa" cuya cuenta de abono es la personal de un contratista registrado | HOLD R05 |
| `28-identity-github-wire.pdf` | GitHub (`card_on_file`) pide pago por transferencia | HOLD R05 |
| `23-category-not-allowed-marketing.pdf` | Marketing no es categoría permitida | REVIEW R07 |
| `24-currency-not-allowed-try.pdf` | Moneda TRY no permitida | REVIEW R09 |
| `29-ambiguous-currency-bare-peso.pdf` | `$ 48.000` sin moneda (nunca inferir) | REVIEW R01 |
| `25-math-mismatch-sur.pdf` | Neto+IVA = 535.500 pero total impreso 585.500 | REVIEW (checker) |
| `35-prompt-injection-invoice.pdf` | Inyección de prompt en el cuerpo de la factura | BLOQUEADA por guardrails |

### Matching de payee (36–37)

| Archivo | Escenario | Veredicto esperado |
|---|---|---|
| `36-alias-long-form-acme.pdf` | "Acme Cloud Incorporated" + EIN correcto | PAY (alias/tax_id) o REVIEW R04 |
| `37-partial-name-no-id.pdf` | "María Rojas" a secas, sin RUT ni cuenta | REVIEW R04 (nombre parcial no se confía) |

### Bordes (30–35, 44–50)

| Archivo | Escenario | Veredicto esperado |
|---|---|---|
| `30-not-bill-order-confirmation.pdf` | Confirmación de compra ya pagada | NO BILL |
| `31-quote-cotizacion.pdf` | Cotización "válida 15 días" | NO BILL |
| `32-credit-note-zero.pdf` | Nota de crédito $0 que anula la 5531 | NO BILL |
| `33-missing-due-date-github.pdf` | Sin fecha de vencimiento | REVIEW R01 |
| `34-noisy-formatting-cuenta.pdf` | Formato sucio: espacios en montos, fecha en palabras | PAY si extrae bien; REVIEW si duda |
| `44-boundary-just-under-autopay.pdf` | USD 999,99 (un centavo bajo el autopago) | PAY |
| `45-boundary-exactly-autopay.pdf` | USD 1.000,00 (= tope, no lo supera) | PAY |
| `46-boundary-exactly-hardcap.pdf` | USD 5.000,00 (= tope duro; > autopago) | REVIEW R13 |
| `47-tiny-amount.pdf` | USD 0,99 | PAY |
| `48-clp-with-cents.pdf` | `$119.000,50` — CLP no admite decimales | REVIEW R01 o PAY si redondea |
| `49-overdue-invoice.pdf` | Vencida hace 1 mes | sin regla específica (decide pagar) |
| `50-future-dated.pdf` | Emitida 2026-12-01 (futura) | borde, sin regla específica |

## Cómo probar el envío por email

1. **Orden sugerido** (los casos con estado dependen de lo enviado antes):
   `01` → `10` (dup exacto) → `11` (fuzzy) → `17` (re-formateado) → `18` (folio alterado) →
   `43` (suscripción) → `04` → `40` (reenvío) → `41` (factura distinta, no dup) →
   `03` → `19` → `42` (monto igual, payee distinto) → `38` → `39` (split) → resto libre.
   Para presupuesto: `01` antes de `16`.
2. Usar remitentes que casen con los identificadores registrados (columna de payees);
   para `22` usar `facturacion@acme-cloud-support.co`; para `40` reenviar `04` desde otra
   casilla (asistente@…) — el contenido idéntico debe caer por hash de documento.
3. Asunto descriptivo, p. ej. `Factura INV-2048 - ACME Cloud`. Un adjunto por email
   (el pipeline toma el primero).

**Límites declarados:** los casos con estado (10, 11, 17, 19, 40, 43, 51, 16, 39) solo
funcionan si envías antes su factura base dentro de la ventana de 45 días — el PDF por sí solo
no fuerza esos veredictos. Los de presupuesto dependen del gasto acumulado del mes.
