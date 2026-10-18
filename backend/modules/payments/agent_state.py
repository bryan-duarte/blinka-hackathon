from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.bills import BillClaim, BillDocument, BillSourceRecord
from contracts.payment_candidates import BillClassification, CandidateExtraction
from contracts.payment_policy import PayeeMatch, PaymentPolicy
from contracts.payments import CheckerAssessment, DecisionRecord
from modules.payments.rules import DecisionContext, RuleEvaluation

TerminalReason = Literal["not_a_bill", "extraction_failed"]


@dataclass
class RunState:
    run_id: UUID
    owner: CurrentUser
    source: BillSourceRecord
    document: BillDocument
    classification: BillClassification | None = None
    extraction: CandidateExtraction | None = None
    policy: PaymentPolicy | None = None
    match: PayeeMatch | None = None
    claim: BillClaim | None = None
    context: DecisionContext | None = None
    evaluation: RuleEvaluation | None = None
    checker_ran: bool = False
    assessment: CheckerAssessment | None = None
    decision: DecisionRecord | None = None
    terminal_reason: TerminalReason | None = None
    agent_error: str | None = None
