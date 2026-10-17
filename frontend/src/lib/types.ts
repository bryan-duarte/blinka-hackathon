export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type MailProvider = "gmail" | "outlook" | "simulated";
export type ConnectableProvider = Exclude<MailProvider, "simulated">;

export type MailAccountStatus = "initiated" | "active" | "failed" | "expired";

export type MailboxConnectStarted = {
  connection_id: string;
  redirect_url: string;
};

export type MailboxConnectionView = {
  connection_id: string;
  provider: MailProvider;
  status: MailAccountStatus;
  created_at: string;
};

export type InboxEmailStatus =
  | "received"
  | "processing"
  | "blocked"
  | "analyzing"
  | "paid"
  | "held"
  | "review"
  | "duplicate"
  | "no_invoice"
  | "no_info"
  | "error";

export type SimulatedEmailKind =
  | "invoice_usd"
  | "invoice_usd_pdf"
  | "invoice_zip_xml"
  | "scanned_pdf"
  | "invoice_clp"
  | "aws_card"
  | "aws_impersonation"
  | "amaz0n_blacklisted"
  | "over_auto_pay"
  | "over_hard_cap"
  | "unknown_payee"
  | "no_currency"
  | "person_cuenta_cobro"
  | "person_cuenta_cobro_second"
  | "agreement_mismatch"
  | "prompt_injection"
  | "plain";

export type Decimal = string;

export type PayeeKind = "service" | "person" | "company";
export type PayeeStatus = "allowed" | "blacklisted";
export type PaymentMethod = "bank_transfer" | "card_on_file" | "platform_debit";
export type PaymentCategory =
  | "cloud"
  | "saas"
  | "contractor"
  | "professional_services"
  | "utilities"
  | "rent"
  | "marketing"
  | "other";
export type IdentifierKind =
  | "tax_id"
  | "bank_account"
  | "service_account_id"
  | "email"
  | "domain"
  | "alias";

export type Verdict = "pay" | "hold" | "review";
export type RuleEffect = "pass" | "hold" | "review";
export type DecisionActor = "agent" | "human";
export type BillStatus =
  | "deciding"
  | "paid"
  | "held"
  | "review"
  | "approving"
  | "rejected"
  | "duplicate";

export type RuleResult = {
  rule_id: string;
  name: string;
  effect: RuleEffect;
  reason: string;
  evidence: Record<string, string>;
};

export type CheckerAnswer = {
  question_id: "CHK1" | "CHK2" | "CHK3";
  probability: number;
  rationale: string;
};

export type CheckerAssessment = { answers: CheckerAnswer[] };

export type FieldEvidence = { field: string; quote: string; confidence: number };

type PaymentCandidateBase = {
  payee_name: string | null;
  amount: Decimal | null;
  currency: string | null;
  issue_date: string | null;
  due_date: string | null;
  invoice_number: string | null;
  description: string | null;
  payee_country: string | null;
  issuer_tax_country: string | null;
  bank_account_country: string | null;
  bank_account: string | null;
  payee_email: string | null;
  category: PaymentCategory | null;
  category_confidence: number;
  embedded_instructions: string[];
  evidence: FieldEvidence[];
};

export type PaymentCandidate =
  | (PaymentCandidateBase & {
      kind: "service";
      provider_domain: string | null;
      service_account_id: string | null;
      billing_period_start: string | null;
      billing_period_end: string | null;
    })
  | (PaymentCandidateBase & {
      kind: "person";
      national_id: string | null;
      concept: string | null;
    })
  | (PaymentCandidateBase & {
      kind: "company";
      legal_name: string | null;
      tax_id: string | null;
      purchase_order: string | null;
    });

export type BillDecisionView = {
  bill_id: string;
  verdict: Verdict;
  status: BillStatus;
  explanation: string;
  rule_results: RuleResult[];
  checker: CheckerAssessment | null;
  candidate: PaymentCandidate | null;
  payee_id: string | null;
  payee_name: string | null;
  amount: Decimal | null;
  currency: string | null;
  amount_usd: Decimal | null;
  category: PaymentCategory | null;
  duplicate_of_bill_id: string | null;
  actor: DecisionActor;
  note: string | null;
  decided_at: string;
  can_approve: boolean;
};

export type PaymentView = {
  payment_id: string;
  status: "reserved" | "executed";
  amount: Decimal;
  currency: string;
  amount_usd: Decimal;
  period: string;
  rail_reference: string | null;
  executed_at: string | null;
};

export type BillSourceType = "email" | "chat" | "upload" | "telegram" | "whatsapp";

export type FileScanStatus = "pending" | "clean" | "threat" | "unsupported" | "failed" | "disabled";

export type EvidenceRole = "archive" | "primary" | "secondary";

export type EvidenceFileView = {
  file_id: string;
  filename: string;
  mime: string;
  size_bytes: number;
  role: EvidenceRole;
  scan_status: FileScanStatus;
  created_at: string;
};

export type RunStatus = "pending" | "running" | "completed" | "failed";

export type PaymentRunEvent = {
  step: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type PaymentRunStatus = {
  run_id: string;
  status: RunStatus;
  error: string | null;
  events: PaymentRunEvent[];
  decision: BillDecisionView | null;
  is_bill: boolean | null;
  extraction_failed: boolean;
  evidence: EvidenceFileView[];
};

export type BillSourceView = {
  source_id: string;
  source_type: BillSourceType;
  source_ref: string;
  sender: string;
  file_id: string | null;
  inbox_email_id: string | null;
  received_at: string | null;
  created_at: string;
};

export type BillDetail = {
  decision: BillDecisionView;
  history: BillDecisionView[];
  sources: BillSourceView[];
  payment: PaymentView | null;
  evidence: EvidenceFileView[];
};

export type BudgetUsageView = {
  scope: string;
  limit_usd: Decimal | null;
  reserved_usd: Decimal;
};

export type PaymentPolicyUpdate = {
  hard_cap_per_payment_usd: Decimal;
  auto_pay_max_usd: Decimal;
  monthly_budget_usd: Decimal;
  category_monthly_budgets_usd: Partial<Record<PaymentCategory, Decimal>>;
  allowed_categories: PaymentCategory[];
  allowed_currencies: string[];
  duplicate_window_days: number;
  min_field_confidence: Decimal;
  min_category_confidence: Decimal;
  checker_review_low: Decimal;
  checker_review_high: Decimal;
};

export type PaymentPolicyView = PaymentPolicyUpdate & {
  policy_id: string;
  version: number;
  created_at: string;
};

export type PayeeIdentifierCreate = { kind: IdentifierKind; value: string };

export type PayeeIdentifierView = {
  identifier_id: string;
  kind: IdentifierKind;
  normalized_value: string;
  raw_value: string;
};

export type PayeeFields = {
  kind: PayeeKind;
  display_name: string;
  status: PayeeStatus;
  payment_method: PaymentMethod;
  default_category: PaymentCategory | null;
  currency: string;
  per_payment_max_usd: Decimal | null;
  monthly_budget_usd: Decimal | null;
  agreed_amount_usd: Decimal | null;
  agreed_tolerance_pct: Decimal | null;
};

export type PayeeCreate = PayeeFields & { identifiers: PayeeIdentifierCreate[] };

export type PayeeUpdate = Partial<Omit<PayeeFields, "kind">> & { version: number };

export type PayeeView = PayeeFields & {
  payee_id: string;
  attributes: Record<string, string>;
  version: number;
  identifiers: PayeeIdentifierView[];
};

export type BlacklistEntryCreate = { kind: IdentifierKind; value: string; reason: string };

export type BlacklistEntryView = {
  entry_id: string;
  kind: IdentifierKind;
  normalized_value: string;
  reason: string;
  created_at: string;
};

export type GuardrailViolation = {
  code: string;
  message: string;
};

export type InboxEmailView = {
  email_id: string;
  provider: MailProvider;
  sender: string;
  subject: string;
  preview: string;
  received_at: string | null;
  status: InboxEmailStatus;
  decision: BillDecisionView | null;
  source_type: BillSourceType;
};

export type InboxEmailDetail = InboxEmailView & {
  body: string;
  violations: GuardrailViolation[];
  error: string | null;
  run_id: string | null;
  evidence: EvidenceFileView[];
};

export const PENDING_STATUSES: ReadonlySet<InboxEmailStatus> = new Set([
  "received",
  "processing",
  "analyzing",
]);
