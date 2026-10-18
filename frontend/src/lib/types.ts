export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type MailProvider = "gmail" | "outlook" | "simulated" | "whatsapp";
export type ConnectableProvider = "gmail" | "outlook";
export type WhatsAppConnectionMode = "sandbox" | "own_number";
export type InboxChannel = "email" | "whatsapp";

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
  mode: WhatsAppConnectionMode | null;
  phone_number: string | null;
  sandbox_number: string | null;
};

export type WhatsAppSandboxView = {
  connection_id: string;
  phone_number: string;
  sandbox_number: string;
  status: MailAccountStatus;
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

export type Decimal = string;

export type FxSource = "identity" | "open_er_api" | "cached" | "static_fallback" | "seed";

export type FxFields = {
  fx_usd_per_unit: Decimal | null;
  fx_rate_date: string | null;
  fx_source: FxSource | null;
};

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

export type BillDecisionView = FxFields & {
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

export type PaymentView = FxFields & {
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
  id: number;
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
  pipeline_stages: PipelineStageRecord[];
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
  pipeline_stages: PipelineStageRecord[];
};

export const PENDING_STATUSES: ReadonlySet<InboxEmailStatus> = new Set([
  "received",
  "processing",
  "analyzing",
]);

export const NOT_A_BILL_STATUSES: ReadonlySet<InboxEmailStatus> = new Set(["no_invoice", "no_info"]);

export type RealtimeEventType =
  | "inbox.item"
  | "pipeline.stage"
  | "run.step"
  | "agent.tool"
  | "agent.todos"
  | "agent.thinking"
  | "agent.rule"
  | "agent.llm";

export type PipelineStage = "queued" | "fetch" | "malware_scan" | "guardrail" | "dedup" | "handoff";

export type PipelineStageStatus = "started" | "finished" | "failed";

export type PipelineStageRecord = {
  stage: PipelineStage;
  status: PipelineStageStatus;
  duration_ms: number | null;
  detail: Record<string, unknown>;
  at?: string;
};

export type RuleOutcome = "pass" | "review" | "hold";

export type RuleEventPayload = {
  code: string;
  name: string;
  outcome: RuleOutcome;
  detail: string;
  evidence?: Record<string, string>;
};

export type ExtractedFieldPayload = {
  name: string;
  value: string | null;
  confidence: number | null;
};

export type ExtractionPayload = {
  method: string;
  fields: ExtractedFieldPayload[];
};

export type FxPayload = {
  amount: string | null;
  currency: string | null;
  amount_usd: string | null;
  usd_per_unit: string | null;
  rate_date: string | null;
  source: FxSource | null;
};

export type CheckerAnswerPayload = {
  question: string;
  probability: number;
  rationale: string;
};

export type CheckerPayload = {
  answers: CheckerAnswerPayload[];
  verdict_after_checker: Verdict;
};

export type AgentLimit = "time" | "tool_calls" | "model_calls";

export type LimitExceededPayload = {
  limit: AgentLimit;
  threshold: number;
};

export type HumanAction = "approved" | "rejected";

export type MemoryView = {
  memory_id: string;
  payee_key: string;
  payee: string;
  situation: string;
  human_action: HumanAction;
  lesson: string;
  applies_when: string | null;
  source_bill_id: string | null;
  note_excerpt: string | null;
  created_at: string;
  updated_at: string;
};

export type LlmCallPayload = {
  node: string;
  parent_tool: string | null;
  model: string;
  input_tokens: number;
  output_tokens: number;
  duration_ms: number;
};

export type RealtimeEvent = {
  type: RealtimeEventType;
  item_id: string | null;
  run_id: string | null;
  step: string;
  payload: Record<string, unknown>;
  message: string | null;
  sequence: number | null;
  created_at: string;
};

export type AgentTodoStatus = "pending" | "in_progress" | "completed";

export type AgentTodo = {
  content: string;
  status: AgentTodoStatus;
};

export type TrustedForwarderKind = "email" | "domain";

export type TrustedForwarderCreate = {
  kind: TrustedForwarderKind;
  value: string;
  note: string | null;
};

export type TrustedForwarderView = {
  forwarder_id: string;
  kind: TrustedForwarderKind;
  normalized_value: string;
  note: string | null;
  created_at: string;
};

export type DemoSectionId = "happy_path" | "formats" | "duplicates" | "rules" | "limits" | "security";

export type DemoExpectation = {
  outcome: InboxEmailStatus;
  rule_ids: string[];
  summary: string;
};

export type DemoScenarioView = {
  scenario_id: string;
  section: DemoSectionId;
  title: string;
  description: string;
  channel: InboxChannel;
  steps: DemoExpectation[];
  is_self_sendable: boolean;
  self_send_hint: string;
};

export type DemoSectionView = {
  section: DemoSectionId;
  title: string;
  scenarios: DemoScenarioView[];
};

export type KitDestinations = {
  email_address: string | null;
  whatsapp_number: string | null;
};

export type DemoCatalogView = {
  company_name: string;
  sections: DemoSectionView[];
  is_guardrail_enforced: boolean;
  is_malware_scan_enabled: boolean;
  destinations: KitDestinations;
};

export type DemoLaunchStatus = "running" | "completed" | "failed" | "cancelled";

export type DemoLaunchStepView = {
  index: number;
  email_id: string | null;
  status: InboxEmailStatus | null;
  expected: DemoExpectation;
  is_as_expected: boolean | null;
};

export type DemoLaunchView = {
  launch_id: string;
  scenario_id: string;
  status: DemoLaunchStatus;
  steps: DemoLaunchStepView[];
  started_at: string;
  error: string | null;
};

export type DemoResetResult = {
  deleted_rows: Record<string, number>;
  deleted_objects: number;
  seeded_bills: number;
  reset_at: string;
};


export type LedgerOutcome =
  | "paid"
  | "escalated"
  | "held"
  | "approved_by_human"
  | "rejected_by_human"
  | "duplicate"
  | "blocked"
  | "not_an_invoice"
  | "missing_info"
  | "error";

export type LedgerTab = "all" | "paid" | "escalated" | "stopped";

export type LedgerFilters = {
  period: string | null;
  tab: LedgerTab;
  payee_id: string | null;
  currency: string | null;
};

export type LedgerReason = {
  rule_id: string;
  name: string;
  effect: RuleEffect;
  reason: string;
};

export type LedgerEntryView = FxFields & {
  entry_id: string;
  occurred_at: string;
  outcome: LedgerOutcome;
  actor: DecisionActor;
  payee_id: string | null;
  payee_name: string | null;
  payee_kind: PayeeKind | null;
  category: PaymentCategory | null;
  amount: Decimal | null;
  currency: string | null;
  amount_usd: Decimal | null;
  reasons: LedgerReason[];
  explanation: string;
  note: string | null;
  channel: BillSourceType | null;
  subject: string | null;
  bill_id: string | null;
  run_id: string | null;
  inbox_email_id: string | null;
  is_seeded: boolean;
};

export type LedgerKpis = {
  paid_count: number;
  paid_usd: Decimal;
  escalated_count: number;
  escalated_usd: Decimal;
  stopped_count: number;
  stopped_usd: Decimal;
  auto_pay_rate: Decimal;
};

export type LedgerTimelinePoint = {
  bucket: string;
  paid: number;
  escalated: number;
  stopped: number;
};

export type LimitUsage = {
  scope: string;
  label: string;
  payee_currency: string | null;
  spent_usd: Decimal;
  limit_usd: Decimal | null;
};

export type ReasonCount = { rule_id: string; name: string; count: number };

export type CurrencyTotal = {
  currency: string;
  amount: Decimal;
  amount_usd: Decimal;
  count: number;
};

export type LedgerSummaryView = {
  period: string;
  kpis: LedgerKpis;
  timeline: LedgerTimelinePoint[];
  limits: LimitUsage[];
  top_reasons: ReasonCount[];
  currencies: CurrencyTotal[];
};

export type RunListItemView = {
  run_id: string;
  status: RunStatus;
  created_at: string;
  duration_ms: number | null;
  channel: BillSourceType | null;
  sender: string | null;
  subject: string | null;
  verdict: Verdict | null;
  bill_id: string | null;
  inbox_email_id: string | null;
  tool_count: number;
  error: string | null;
};

export type TraceRole = "system" | "human" | "ai" | "tool";

export type TraceToolCall = {
  call_id: string;
  name: string;
  args: Record<string, unknown>;
};

export type TraceMessage = {
  index: number;
  role: TraceRole;
  text: string;
  tool_calls: TraceToolCall[];
  tool_call_id: string | null;
  tool_name: string | null;
  output_json: Record<string, unknown> | unknown[] | null;
};

export type RunTraceView = {
  run_id: string;
  is_available: boolean;
  checkpoint_id: string | null;
  messages: TraceMessage[];
};
