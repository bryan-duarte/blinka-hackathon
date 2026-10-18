import type {
  AgentTodoStatus,
  BillSourceType,
  DecisionActor,
  DemoSectionId,
  EvidenceRole,
  FileScanStatus,
  FxSource,
  IdentifierKind,
  InboxEmailStatus,
  LedgerOutcome,
  PayeeKind,
  PayeeStatus,
  PaymentCategory,
  PaymentMethod,
  PipelineStage,
  RuleOutcome,
  RunStatus,
  TraceRole,
  Verdict,
} from "./types";

export const CATEGORY_LABELS: Record<PaymentCategory, string> = {
  cloud: "Cloud",
  saas: "Software (SaaS)",
  contractor: "Contractors",
  professional_services: "Professional services",
  utilities: "Utilities",
  rent: "Rent",
  marketing: "Marketing",
  other: "Other",
};

export const PAYMENT_CATEGORIES = Object.keys(CATEGORY_LABELS) as PaymentCategory[];

export const PAYEE_KIND_LABELS: Record<PayeeKind, string> = {
  service: "Service",
  person: "Person",
  company: "Company",
};

export const PAYEE_KIND_GROUP_LABELS: Record<PayeeKind, string> = {
  service: "Services",
  person: "People",
  company: "Companies",
};

export const PAYEE_STATUS_LABELS: Record<PayeeStatus, string> = {
  allowed: "Allowed",
  blacklisted: "Blocked",
};

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  bank_transfer: "Bank transfer",
  card_on_file: "Card on file",
  platform_debit: "Platform debit",
};

export const IDENTIFIER_KIND_LABELS: Record<IdentifierKind, string> = {
  tax_id: "Tax ID",
  bank_account: "Bank account",
  service_account_id: "Service account",
  email: "Email",
  domain: "Domain",
  alias: "Name or alias",
};

export const IDENTIFIER_KINDS = Object.keys(IDENTIFIER_KIND_LABELS) as IdentifierKind[];

export const VERDICT_LABELS: Record<Verdict, string> = {
  pay: "Paid",
  hold: "Held",
  review: "In review",
};

export const ACTOR_LABELS: Record<DecisionActor, string> = {
  agent: "Agent",
  human: "Person",
};

export const FIELD_LABELS: Record<string, string> = {
  payee_name: "Payee",
  amount: "Amount",
  currency: "Currency",
  payee_country: "Payee country",
  issuer_tax_country: "Issuer tax country",
  bank_account_country: "Account country",
  due_date: "Due date",
  issue_date: "Issue date",
  invoice_number: "Invoice no.",
  bank_account: "Destination account",
  payee_email: "Payee email",
  service_account_id: "Service account",
  provider_domain: "Domain",
  national_id: "National ID",
  tax_id: "Tax ID",
  legal_name: "Legal name",
  concept: "Concept",
};

export const SOURCE_LABELS: Record<BillSourceType, string> = {
  email: "Email",
  upload: "Console",
  chat: "Chat",
  telegram: "Telegram",
  whatsapp: "WhatsApp",
};

export const EVIDENCE_ROLE_LABELS: Record<EvidenceRole, string> = {
  primary: "Data source",
  secondary: "Supporting copy",
  archive: "Received ZIP file",
};

export const SCAN_LABELS: Record<FileScanStatus, string> = {
  clean: "Scanned by AWS",
  unsupported: "Not scanned",
  disabled: "Not scanned",
  pending: "Scan pending",
  threat: "Threat detected",
  failed: "Scan failed",
};

export const TODO_STATUS_LABELS: Record<AgentTodoStatus, string> = {
  pending: "Pending",
  in_progress: "In progress",
  completed: "Done",
};

export const EXTRACTION_METHOD_LABELS: Record<string, string> = {
  xml: "XML e-invoice",
  xml_llm: "XML read by the model",
  textract: "AWS Textract reading",
  pdf_text: "PDF text read by the model",
  pdf: "PDF read by the model",
  email: "message text",
};

export const INBOX_STATUS_LABELS: Record<InboxEmailStatus, string> = {
  received: "Received",
  processing: "Processing",
  blocked: "Blocked",
  analyzing: "Analyzing",
  paid: "Paid",
  held: "Held",
  review: "In review",
  duplicate: "Duplicate",
  no_invoice: "Not an invoice",
  no_info: "Missing information",
  error: "Error",
};

export const LEDGER_OUTCOME_LABELS: Record<LedgerOutcome, string> = {
  paid: "Paid",
  escalated: "Escalated to a person",
  held: "Held",
  approved_by_human: "Approved by a person",
  rejected_by_human: "Rejected by a person",
  duplicate: "Duplicate",
  blocked: "Blocked",
  not_an_invoice: "Not an invoice",
  missing_info: "Missing information",
  error: "Error",
};

export const FX_SOURCE_LABELS: Record<FxSource, string> = {
  identity: "USD",
  open_er_api: "Live rate · ExchangeRate-API",
  cached: "Cached rate",
  static_fallback: "Fallback rate",
  seed: "Historical rate",
};

export const DEMO_SECTION_LABELS: Record<DemoSectionId, string> = {
  happy_path: "Happy path",
  formats: "Formats",
  duplicates: "Duplicates",
  rules: "Rules & agreements",
  limits: "Limits & budget",
  security: "Security",
};

export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

export const TRACE_ROLE_LABELS: Record<TraceRole, string> = {
  system: "System prompt",
  human: "Task",
  ai: "Agent",
  tool: "Tool result",
};

export const RULE_LABELS: Record<string, string> = {
  R01: "Complete data",
  R02: "No embedded instructions",
  R03: "Not blacklisted",
  R04: "Registered payee",
  R05: "Consistent identity",
  R05b: "Known sender",
  R06: "Payee kind matches",
  R07: "Category allowed",
  R08: "Category confident",
  R09: "Currency allowed",
  R11: "No probable duplicate",
  R12: "Per-payment cap",
  R13: "Auto-pay limit",
  R14: "Budget available",
  R17: "Matches agreement",
  R18: "Tax identity consistent",
  CHK1: "Checker: service matches",
  CHK2: "Checker: impersonation",
  CHK3: "Checker: usual amount",
  DUP: "Exact duplicate",
  PAY: "Payment execution",
  ERR: "Technical error",
  GUARD: "Guardrail",
  MALWARE: "Malware scan",
  INTAKE: "Unreadable attachment",
};

export function ruleLabel(ruleId: string): string {
  return RULE_LABELS[ruleId] ?? ruleId;
}

export const POLICY_RULE_IDS = Object.keys(RULE_LABELS).filter((ruleId) => /^R\d/.test(ruleId));

export const STAGE_LABELS: Record<PipelineStage, string> = {
  queued: "Queued",
  fetch: "Fetched the message",
  malware_scan: "Malware scan",
  guardrail: "Guardrail check",
  dedup: "Duplicate check",
  handoff: "Handed to the agent",
};

export const INTAKE_SCAN_LABELS: Record<string, string> = {
  ready: "clean",
  malware: "threat found",
  scan_failed: "scan did not finish",
  unreadable: "unreadable file",
};

export type AgentPhase = "intake" | "classify" | "extract" | "register" | "rules" | "checker" | "settle";

export const PHASE_LABELS: Record<AgentPhase, string> = {
  intake: "Intake",
  classify: "Classify",
  extract: "Extract",
  register: "Register",
  rules: "Rules",
  checker: "Checker",
  settle: "Decide",
};

export const RULE_OUTCOME_LABELS: Record<RuleOutcome, string> = {
  pass: "Passed",
  review: "Needs a person",
  hold: "Blocks",
};
