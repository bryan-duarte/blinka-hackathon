# Frontend Inbox Implementation

## Overview

This is a temporary three-page Next.js UI:
- login and register
- an inbox with mailbox connections, a simulate menu, the email list and a detail pane showing the guardrail verdict and CLP analysis
- the OAuth callback page

The browser calls FastAPI directly through `NEXT_PUBLIC_API_URL`. The backend handles CORS.

## Files to Modify/Create

- `frontend/.env.example` (new): `NEXT_PUBLIC_API_URL=http://localhost:8000`. Also tell the user to copy it to `.env.local`.
- `frontend/src/lib/types.ts` (new): TypeScript mirrors of the API contracts:
  - `TokenResponse`, `MailProvider`, `MailAccountStatus`, `MailboxConnectStarted`, `MailboxConnectionView`
  - `InboxEmailStatus`, `SimulatedEmailKind`, `InvoiceClpAnalysis`, `GuardrailViolation`, `InboxEmailView`, `InboxEmailDetail`
- `frontend/src/lib/api.ts` (new): the API client.
- `frontend/src/app/page.tsx`: replace the placeholder with a client redirect. With a token it goes to `/inbox`; without one it goes to `/login`.
- `frontend/src/app/login/page.tsx` (new).
- `frontend/src/app/inbox/page.tsx` (new).
- `frontend/src/app/inbox/callback/page.tsx` (new).
- `frontend/src/components/inbox/ConnectionBar.tsx`, `EmailList.tsx`, `EmailDetail.tsx`, `StatusBadge.tsx` (new).
- `frontend/src/app/layout.tsx`: set the metadata title to "Blinka Inbox". Nothing else changes.

## Implementation Guidelines

- Invoke the `frontend-design` skill before writing components. No design system exists yet, so commit to a clean, minimal look using Tailwind v4 utilities.
- No new npm dependencies.
- Pages that use browser APIs are `"use client"`.
- UI copy is in Spanish (e.g. "Conectar Gmail", "Simular correo", "Bloqueado por guardrails").

### `lib/api.ts`

This snippet is orientative.

```ts
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "blinka_token";

export const tokenStore = {
  get: () => (typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY)),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class UnauthorizedError extends Error {}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = tokenStore.get();
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers },
  });
  if (response.status === 401) { tokenStore.clear(); throw new UnauthorizedError(); }
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail ?? response.statusText);
  return response.json() as Promise<T>;
}

export const api = {
  login: (email: string, password: string) => request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string) => request<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  connect: (provider: "gmail" | "outlook") => request<MailboxConnectStarted>("/inbox/connections", { method: "POST", body: JSON.stringify({ provider }) }),
  confirm: (connected_account_id: string) => request<MailboxConnectionView>("/inbox/connections/confirm", { method: "POST", body: JSON.stringify({ connected_account_id }) }),
  connections: () => request<MailboxConnectionView[]>("/inbox/connections"),
  emails: () => request<InboxEmailView[]>("/inbox/emails"),
  email: (id: string) => request<InboxEmailDetail>(`/inbox/emails/${id}`),
  simulate: (kind: SimulatedEmailKind) => request<InboxEmailView>("/inbox/simulate", { method: "POST", body: JSON.stringify({ kind }) }),
};
```

Pages catch `UnauthorizedError` and call `router.replace("/login")`.

### `/login`

- An email and password form with a toggle between "Ingresar" and "Crear cuenta".
- On success, call `tokenStore.set(access_token)` and go to `/inbox`.
- Show the backend `detail` on error, e.g. 409 "email already registered".

### `/inbox`

**Layout**
- Top bar: `ConnectionBar` plus a "Simular correo" menu with the four `SimulatedEmailKind` values, plus a logout button.
- Main area: two columns. `EmailList` on the left, `EmailDetail` for the selected email on the right.
- On narrow screens, use a single column. Selecting an email shows its detail with a back button.

**`ConnectionBar`**
- One chip per connection: provider plus status.
- Buttons "Conectar Gmail" and "Conectar Outlook", hidden when that provider is already `active`. They call `api.connect(provider)` and then `window.location.href = redirect_url`.
- A 409 response shows "ya conectado".

**Polling**
- `useEffect` loads `connections()` and `emails()` once.
- Then a `setInterval(4000)` reloads `emails()`, plus the selected email's detail, while any email has status `received`, `processing` or `analyzing`.
- Clear the interval when none are pending or on unmount.
- After `simulate`, reload immediately.

**`EmailList`**
- Each row shows sender, subject, preview, relative `received_at` (or "simulado"), a `StatusBadge`, and `analysis.amount_clp` formatted with `new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP" })` when present.

**`StatusBadge` labels**

| Status | Label | Colour |
|---|---|---|
| `received` / `processing` | "Recibido" / "Revisando" | neutral, with a pulse |
| `blocked` | "Bloqueado" | red |
| `analyzing` | "Analizando" | amber, with a pulse |
| `analyzed` | "Analizado" | green |
| `no_invoice` | "Sin factura" | gray |
| `error` | "Error" | red outline |

**`EmailDetail`**
- Header: subject, sender, date.
- Body in a `whitespace-pre-wrap` block.
- Then one result card, depending on status:
  - `blocked`: the list of violations (`code` and `message`) and the text "No se ejecutó ningún agente".
  - `analyzed`: vendor, `invoice_number`, original amount and currency, `clp_rate`, a large `amount_clp` in CLP, and `summary`.
  - `no_invoice`: `analysis?.summary` or the run error.
  - `error`: the `error` text.
  - pending statuses: a spinner line.

### `/inbox/callback`

- Read `connected_account_id` and `status` with `useSearchParams()`. Wrap the page in `<Suspense>`, which Next 16 requires for `useSearchParams` in client pages.
- If `status !== "success"` or the id is missing, show an error and a link back to `/inbox`.
- Otherwise call `api.confirm(id)` up to 10 times, 1 second apart, until `status !== "initiated"`.
- When the result is `active`, call `router.replace("/inbox")`. Otherwise show the final status.

## Dependencies

- Backend routes from spec 06.
- `next 16.4.2`, `react 19.3.1`, `tailwindcss 4.3.3`, all already installed.

## Integration Notes

- The JSON field names are the backend's snake_case names. Do not remap them.
- `received_at` and `created_at` are ISO strings.
- The backend's default `callback_url` is `http://localhost:3000/inbox/callback`. The callback route must exist at exactly that path.
