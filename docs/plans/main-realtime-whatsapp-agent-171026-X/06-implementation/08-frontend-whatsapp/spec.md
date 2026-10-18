# Frontend WhatsApp Implementation

## Overview

Add the frontend pieces for WhatsApp: a connection card (sandbox by default, own number opt-in), the Kapso callback page, simulated WhatsApp samples, a source filter, and channel-neutral inbox copy.

## Files to Modify/Create

- `frontend/src/lib/types.ts`
  - `MailProvider` gains `"whatsapp"`.
  - New types `WhatsAppConnectionMode`, `InboxSourceFilter`, `SandboxActivation`, `WhatsAppSandboxView`.
  - `MailboxConnectionView` gains `mode` and `phone_number`.
- `frontend/src/lib/api.ts`, in the `api` object:
  - `registerWhatsAppSandbox(phone_number: string): Promise<WhatsAppSandboxView>` → `POST /inbox/whatsapp/sandbox`
  - `connectWhatsAppNumber(): Promise<MailboxConnectStarted>` → `POST /inbox/whatsapp/own-number`
  - `confirmWhatsApp(setup_link_id: string, phone_number_id: string): Promise<MailboxConnectionView>` → `POST /inbox/whatsapp/confirm`
  - `emails(source?: InboxSourceFilter)` appends `?source=` when the argument is set.
  - `simulate(kind, channel: "email" | "whatsapp" = "email")`.
- `frontend/src/components/inbox/WhatsAppCard.tsx` (new): `WhatsAppCard({ connections, onUnauthorized, onChanged })`.
- `frontend/src/components/inbox/ConnectionBar.tsx`: render `<WhatsAppCard …/>` after the mail providers. Exclude `provider === "whatsapp"` rows from the existing mail chips.
- `frontend/src/app/inbox/whatsapp/callback/page.tsx` (new): handle the Kapso redirect.
- `frontend/src/app/inbox/page.tsx`
  - `SIMULATION_OPTIONS` (`:24-42`) gets a second group, "WhatsApp", built from the kinds that carry a document (mirror the backend `WHATSAPP_SIMULATABLE_KINDS`: `invoice_usd_pdf`, `invoice_zip_xml`, `scanned_pdf`, plus any other kind with attachments, checked against `backend/modules/inbox/samples.py`).
  - Add `sourceFilter` state (`InboxSourceFilter | null`) and pass it to `api.emails`.
  - Filter chips "Todos · Correo · WhatsApp".
- `frontend/src/lib/labels.ts`
  - `EXTRACTION_METHOD_LABELS.email` changes from "cuerpo del correo" to "texto del mensaje".
  - Add `SOURCE_FILTER_LABELS`.
- Copy changes (channel-neutral Spanish):
  - `app/inbox/page.tsx`: "correos" → "mensajes", "Simular correo" → "Simular mensaje".
  - `components/inbox/EmailDetail.tsx`: "Detalle del correo" → "Detalle del mensaje", "Revisando el correo y escaneando adjuntos con AWS..." → "Revisando el mensaje y escaneando documentos con AWS…".
  - `components/inbox/EmailList.tsx`: keep the "simulado" fallback.

## Implementation Guidelines

- **Before writing code,** read `frontend/DESIGN.md` fully and follow it strictly:
  - card: white on paper, 1 px line, 4 px radius, 32 px padding, no shadow
  - one cobalt primary paired with a ghost secondary
  - weight 300, labels at 14 px/400
  - left aligned
  - no em-dashes in UI copy
  - reuse the `components/settings/styles.ts` constants (`CARD_CLASS`, `PRIMARY_BUTTON_CLASS`, `SECONDARY_BUTTON_CLASS`, `INPUT_CLASS`, `EYEBROW_CLASS`)
- **WhatsAppCard states.** The active sandbox and own-number rows come from `connections`, filtered by `provider === "whatsapp"`.

  | State | Content |
  |---|---|
  | **Own number active** (`mode=own_number`, status active) | Eyebrow "WhatsApp". Line "Conectado: {phone_number}". Quiet text "Escaneamos los documentos que recibe tu número". |
  | **Sandbox active** (`mode=sandbox`, status active) | Line "Modo demo (sandbox)". Text "Reenvía tus facturas en PDF, ZIP o XML al número {sandbox_number} desde {phone_number}". The ghost button "Conectar mi número" leads to the own-number flow. |
  | **Sandbox not registered** (default) | Text "Por defecto usamos el número demo de Blinka". A phone input (`type="tel"`, placeholder "+56 9 1234 5678") with the primary button "Activar demo", which calls `api.registerWhatsAppSandbox`. Ghost button "Conectar mi número". |

  After registration (component-local state holding the `WhatsAppSandboxView`):
  - If `activation` is set, show "Envía este código desde tu WhatsApp: **{activation_code}**", plus a primary link "Abrir WhatsApp" (`href=activation_link`, `target="_blank"`, `rel="noopener noreferrer"`). The code expires in 15 minutes; show that as quiet text.
  - If `activation === null`, show the manual fallback: "Escríbele al número {sandbox_number} con el código de activación que te compartimos desde el panel de Kapso".
  - Then call `onChanged()` so the page reloads connections.
- **"Conectar mi número"** calls `api.connectWhatsAppNumber()`, then `window.location.assign(redirect_url)`. Mirror `ConnectionBar.connect` for errors: 409 means "WhatsApp ya conectado"; anything else means "No se pudo iniciar la conexión".
- **Callback page** (`/inbox/whatsapp/callback`): mirror `app/inbox/callback/page.tsx`.
  1. Read `setup_link_id`, `status`, `phone_number_id` and `error_code` from `useSearchParams` (wrap in `<Suspense>` as the existing callback does).
  2. On `status=completed`, call `api.confirmWhatsApp(setup_link_id, phone_number_id)` once, then `router.replace("/inbox")`.
  3. On `error_code`, show the mapped Spanish message plus a link back to the inbox:

     | `error_code` | Message |
     |---|---|
     | `facebook_auth_failed` | "No se pudo autenticar con Meta" |
     | `phone_verification_failed` | "No se pudo verificar el número" |
     | `link_expired` | "El enlace expiró, vuelve a intentarlo" |
     | `already_used` | "Este enlace ya se usó" |
     | otherwise | "No se pudo conectar WhatsApp" |
- **Source filter chips.** `rounded-full` tags as DESIGN.md specifies. The selected chip uses `bg-accent-wash text-accent`. Changing the filter resets `selectedEmailId` if the selected item is no longer in the list.
- **Badges.** `SourceBadge` already has a `whatsapp` glyph and label, so no change is needed.

## Dependencies

- Module 06 (endpoints and `source` filter) and module 07 (realtime is unaffected; WhatsApp items arrive as `inbox.item` events like any other).

## Integration Notes

- Kapso appends `setup_link_id`, `status`, `phone_number_id`, `business_account_id`, `display_phone_number` (success) or `setup_link_id`, `error_code` (failure) to `BLINKA_KAPSO__CALLBACK_URL`. These are untrusted hints; the backend verifies the phone number.
- The connection list endpoint is unchanged: `GET /inbox/connections` returns WhatsApp rows alongside mail rows.
