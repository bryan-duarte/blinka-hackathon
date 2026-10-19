import type {
  BillDecisionView,
  BillDetail,
  BillStatus,
  BlacklistEntryCreate,
  BlacklistEntryView,
  BudgetUsageView,
  ConnectableProvider,
  DemoCatalogView,
  DemoLaunchView,
  DemoResetResult,
  EvidenceFileView,
  InboxChannel,
  InboxEmailDetail,
  InboxEmailView,
  LedgerEntryView,
  LedgerFilters,
  LedgerSummaryView,
  MailboxConnectionView,
  MailboxConnectStarted,
  MemoryView,
  PayeeCreate,
  PayeeIdentifierCreate,
  PayeeUpdate,
  PayeeView,
  PaymentPolicyUpdate,
  PaymentPolicyView,
  PaymentRunStatus,
  RunListItemView,
  RunStatus,
  RunTraceView,
  TokenResponse,
  TrustedForwarderCreate,
  TrustedForwarderView,
  WhatsAppSandboxView,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "blinka_token";
const HTTP_UNAUTHORIZED = 401;
const HTTP_NO_CONTENT = 204;
export const HTTP_CONFLICT = 409;
const PDF_MIME = "application/pdf";
const XML_MIMES: ReadonlySet<string> = new Set(["application/xml", "text/xml"]);
const PLAIN_TEXT_MIME = "text/plain;charset=utf-8";
const OBJECT_URL_TTL_MS = 60_000;

export const tokenStore = {
  get: (): string | null =>
    typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export function currentUserId(): string | null {
  const token = tokenStore.get();
  const encodedClaims = token?.split(".")[1];
  if (!encodedClaims) return null;
  try {
    const claimsJson = atob(encodedClaims.replace(/-/g, "+").replace(/_/g, "/"));
    const claims: unknown = JSON.parse(claimsJson);
    const subject = claims && typeof claims === "object" && "sub" in claims ? claims.sub : null;
    return typeof subject === "string" ? subject : null;
  } catch {
    return null;
  }
}

export class UnauthorizedError extends Error {}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function errorDetail(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null);
  const detail =
    body && typeof body === "object" && "detail" in body ? body.detail : null;
  return typeof detail === "string" ? detail : response.statusText;
}

async function authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = tokenStore.get();
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (response.status === HTTP_UNAUTHORIZED && token) {
    tokenStore.clear();
    throw new UnauthorizedError();
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorDetail(response));
  }
  return response;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await authorizedFetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (response.status === HTTP_NO_CONTENT) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function fileBlob(fileId: string): Promise<Blob> {
  const response = await authorizedFetch(`/files/${fileId}/content`);
  return response.blob();
}

function inlineSafeMime(mime: string): string | null {
  if (mime === PDF_MIME) return PDF_MIME;
  if (XML_MIMES.has(mime)) return PLAIN_TEXT_MIME;
  return null;
}

async function openFile(file: EvidenceFileView): Promise<void> {
  const inlineMime = inlineSafeMime(file.mime);
  const viewerTab = inlineMime ? window.open("", "_blank") : null;
  try {
    const fileContent = await fileBlob(file.file_id);
    const objectUrl = URL.createObjectURL(new Blob([fileContent], { type: inlineMime ?? file.mime }));
    if (viewerTab) {
      viewerTab.location.href = objectUrl;
    } else {
      const downloadLink = document.createElement("a");
      downloadLink.href = objectUrl;
      downloadLink.download = file.filename;
      downloadLink.click();
    }
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), OBJECT_URL_TTL_MS);
  } catch (error) {
    viewerTab?.close();
    throw error;
  }
}

async function downloadBlob(path: string, filename: string): Promise<void> {
  const response = await authorizedFetch(path);
  const objectUrl = URL.createObjectURL(await response.blob());
  const downloadLink = document.createElement("a");
  downloadLink.href = objectUrl;
  downloadLink.download = filename;
  downloadLink.click();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), OBJECT_URL_TTL_MS);
}

function ledgerQuery(filters: LedgerFilters): string {
  const query = new URLSearchParams({ tab: filters.tab });
  if (filters.period) query.set("period", filters.period);
  if (filters.payee_id) query.set("payee_id", filters.payee_id);
  if (filters.currency) query.set("currency", filters.currency);
  return query.toString();
}

function send<T>(method: "POST" | "PUT" | "PATCH", path: string, payload: object): Promise<T> {
  return request<T>(path, { method, body: JSON.stringify(payload) });
}

function post<T>(path: string, payload: object): Promise<T> {
  return send<T>("POST", path, payload);
}

function remove(path: string): Promise<void> {
  return request<void>(path, { method: "DELETE" });
}

export const api = {
  login: (email: string, password: string) =>
    post<TokenResponse>("/auth/login", { email, password }),
  connect: (provider: ConnectableProvider) =>
    post<MailboxConnectStarted>("/inbox/connections", { provider }),
  confirm: (connected_account_id: string) =>
    post<MailboxConnectionView>("/inbox/connections/confirm", {
      connected_account_id,
    }),
  connections: () => request<MailboxConnectionView[]>("/inbox/connections"),
  registerWhatsAppSandbox: (phone_number: string) =>
    post<WhatsAppSandboxView>("/inbox/whatsapp/sandbox", { phone_number }),
  connectWhatsAppNumber: () =>
    post<MailboxConnectStarted>("/inbox/whatsapp/own-number", {}),
  confirmWhatsApp: (setup_link_id: string, phone_number_id: string) =>
    post<MailboxConnectionView>("/inbox/whatsapp/confirm", { setup_link_id, phone_number_id }),
  emails: (source?: InboxChannel) =>
    request<InboxEmailView[]>(source ? `/inbox/emails?source=${source}` : "/inbox/emails"),
  email: (emailId: string) =>
    request<InboxEmailDetail>(`/inbox/emails/${emailId}`),
  policy: () => request<PaymentPolicyView>("/payment-policy"),
  updatePolicy: (body: PaymentPolicyUpdate) =>
    send<PaymentPolicyView>("PUT", "/payment-policy", body),
  payees: () => request<PayeeView[]>("/payees"),
  createPayee: (body: PayeeCreate) => post<PayeeView>("/payees", body),
  updatePayee: (payeeId: string, body: PayeeUpdate) =>
    send<PayeeView>("PATCH", `/payees/${payeeId}`, body),
  deletePayee: (payeeId: string) => remove(`/payees/${payeeId}`),
  addIdentifier: (payeeId: string, body: PayeeIdentifierCreate) =>
    post<PayeeView>(`/payees/${payeeId}/identifiers`, body),
  deleteIdentifier: (payeeId: string, identifierId: string) =>
    remove(`/payees/${payeeId}/identifiers/${identifierId}`),
  blacklist: () => request<BlacklistEntryView[]>("/blacklist"),
  addBlacklist: (body: BlacklistEntryCreate) =>
    post<BlacklistEntryView>("/blacklist", body),
  deleteBlacklist: (entryId: string) => remove(`/blacklist/${entryId}`),
  bills: (status?: BillStatus) =>
    request<BillDecisionView[]>(status ? `/bills?status=${status}` : "/bills"),
  bill: (billId: string) => request<BillDetail>(`/bills/${billId}`),
  approveBill: (billId: string, note: string, remember: boolean) =>
    post<BillDecisionView>(`/bills/${billId}/approve`, { note, remember }),
  rejectBill: (billId: string, note: string, remember: boolean) =>
    post<BillDecisionView>(`/bills/${billId}/reject`, { note, remember }),
  memories: () => request<MemoryView[]>("/memories"),
  deleteMemory: (payeeKey: string, memoryId: string) =>
    remove(`/memories/${encodeURIComponent(payeeKey)}/${encodeURIComponent(memoryId)}`),
  budgets: (period?: string) =>
    request<BudgetUsageView[]>(period ? `/budgets?period=${period}` : "/budgets"),
  runStatus: (runId: string) => request<PaymentRunStatus>(`/payments/runs/${runId}`),
  runTrace: (runId: string) => request<RunTraceView>(`/payments/runs/${runId}/trace`),
  run: (runId: string) => request<RunListItemView>(`/runs/${runId}`),
  runs: (status?: RunStatus) => request<RunListItemView[]>(status ? `/runs?status=${status}` : "/runs"),
  ledgerEntries: (filters: LedgerFilters) =>
    request<LedgerEntryView[]>(`/ledger/entries?${ledgerQuery(filters)}`),
  ledgerSummary: (period: string | null, months: number) =>
    request<LedgerSummaryView>(
      `/ledger/summary?months=${months}${period ? `&period=${period}` : ""}`,
    ),
  exportLedgerCsv: (filters: LedgerFilters) =>
    downloadBlob(
      `/ledger/export.csv?${ledgerQuery(filters)}`,
      `agent-ledger-${filters.period ?? "all"}.csv`,
    ),
  demoCatalog: () => request<DemoCatalogView>("/demo/scenarios"),
  launchScenario: (scenarioId: string) =>
    post<DemoLaunchView>(`/demo/scenarios/${scenarioId}/launch`, {}),
  demoLaunch: (launchId: string) => request<DemoLaunchView>(`/demo/launches/${launchId}`),
  resetDemo: () => post<DemoResetResult>("/demo/reset", {}),
  downloadDemoKit: () => downloadBlob("/demo/kit", "andescape-demo-kit.zip"),
  downloadScenarioKit: (scenarioId: string) =>
    downloadBlob(`/demo/scenarios/${scenarioId}/kit`, `${scenarioId}.zip`),
  trustedForwarders: () => request<TrustedForwarderView[]>("/trusted-forwarders"),
  addTrustedForwarder: (body: TrustedForwarderCreate) =>
    post<TrustedForwarderView>("/trusted-forwarders", body),
  deleteTrustedForwarder: (forwarderId: string) => remove(`/trusted-forwarders/${forwarderId}`),
  openFile,
  downloadFile: (file: EvidenceFileView) => downloadBlob(`/files/${file.file_id}/content`, file.filename),
};

export function canViewInBrowser(file: EvidenceFileView): boolean {
  return inlineSafeMime(file.mime) !== null;
}
