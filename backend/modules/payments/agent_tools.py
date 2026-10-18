import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from langchain_core.tools import BaseTool, StructuredTool

from contracts.bills import BillClaim, BillFields, BillStatus
from contracts.fx import FxQuote
from contracts.payment_candidates import PaymentCandidateBase
from contracts.payment_policy import PayeeMatch
from contracts.payments import DecisionActor, RuleEffect, Verdict
from core.logging_config import get_logger
from modules.invoice_ingestor import InvoiceParseError
from modules.payments import checker
from modules.payments.agent_state import RunState
from modules.payments.context_builder import build_context
from modules.payments.dependencies import PaymentRunDependencies
from modules.payments.events import (
    CLAIMED_STEP,
    CLASSIFIED_STEP,
    DECIDED_STEP,
    EXTRACTED_STEP,
    EXTRACTION_FAILED_STEP,
    NOT_A_BILL_STEP,
    RunEventRecorder,
)
from modules.payments.rules import decide
from modules.payments.settlement import record_duplicate, settle

logger = get_logger(__name__)

ISO_CURRENCY_CODE = re.compile(r"[A-Z]{3}")

CLASSIFY_DOCUMENT_TOOL = "classify_document"
EXTRACT_INVOICE_TOOL = "extract_invoice"
REGISTER_BILL_TOOL = "register_bill"
EVALUATE_RULES_TOOL = "evaluate_rules"
RUN_CHECKER_TOOL = "run_checker"
SETTLE_DECISION_TOOL = "settle_decision"
STEP_TOOL_NAMES = frozenset(
    {
        CLASSIFY_DOCUMENT_TOOL,
        EXTRACT_INVOICE_TOOL,
        REGISTER_BILL_TOOL,
        EVALUATE_RULES_TOOL,
        RUN_CHECKER_TOOL,
        SETTLE_DECISION_TOOL,
    }
)
TOOL_DESCRIPTIONS = {
    CLASSIFY_DOCUMENT_TOOL: (
        "Step 1. Classify the received document as a payable bill or not. Takes no input."
    ),
    EXTRACT_INVOICE_TOOL: (
        "Step 2. Extract payee, amount, currency, invoice number and due date from the "
        "classified bill. Takes no input."
    ),
    REGISTER_BILL_TOOL: (
        "Step 3. Match the payee against the allow list and register the bill, detecting "
        "exact duplicates. Takes no input."
    ),
    EVALUATE_RULES_TOOL: (
        "Step 4. Evaluate the company's deterministic payment rules on the registered bill. "
        "Takes no input."
    ),
    RUN_CHECKER_TOOL: (
        "Step 5. Run the independent second review. Required before settling when the rules "
        "allow paying; skipped otherwise. Takes no input."
    ),
    SETTLE_DECISION_TOOL: (
        "Step 6. Record the final decision computed by the rules and the checker. Takes no input."
    ),
}
CHECKER_SKIPPED_REASON = "only applies when the rules allow paying"

StepCoroutine = Callable[[], Awaitable[str]]


class PaymentStepTools:
    def __init__(
        self,
        state: RunState,
        dependencies: PaymentRunDependencies,
        events: RunEventRecorder,
    ) -> None:
        self._state = state
        self._dependencies = dependencies
        self._events = events
        self._step_lock = asyncio.Lock()

    def as_tools(self) -> list[BaseTool]:
        step_coroutines = {
            CLASSIFY_DOCUMENT_TOOL: self.classify_document,
            EXTRACT_INVOICE_TOOL: self.extract_invoice,
            REGISTER_BILL_TOOL: self.register_bill,
            EVALUATE_RULES_TOOL: self.evaluate_rules,
            RUN_CHECKER_TOOL: self.run_checker,
            SETTLE_DECISION_TOOL: self.settle_decision,
        }
        return [
            StructuredTool.from_function(
                coroutine=coroutine, name=name, description=TOOL_DESCRIPTIONS[name]
            )
            for name, coroutine in step_coroutines.items()
        ]

    async def _run_serialized(self, step: StepCoroutine) -> str:
        # Parallel tool calls must not interleave: every guard is check-then-await-then-set.
        async with self._step_lock:
            return await step()

    async def classify_document(self) -> str:
        return await self._run_serialized(self._classify_document)

    async def extract_invoice(self) -> str:
        return await self._run_serialized(self._extract_invoice)

    async def register_bill(self) -> str:
        return await self._run_serialized(self._register_bill)

    async def evaluate_rules(self) -> str:
        return await self._run_serialized(self._evaluate_rules)

    async def run_checker(self) -> str:
        return await self._run_serialized(self._run_checker)

    async def settle_decision(self) -> str:
        return await self._run_serialized(self._settle_decision)

    async def _classify_document(self) -> str:
        state = self._state
        if state.classification is not None:
            return _out_of_order("The document was already classified.", state)
        classification = await self._dependencies.invoice_ingestor.classify(
            state.owner, state.document
        )
        state.classification = classification
        await self._events.step(CLASSIFIED_STEP, classification.model_dump(mode="json"))
        summary = {
            "is_bill": classification.is_bill,
            "kind": classification.kind,
            "confidence": classification.confidence,
            "reason": classification.reason,
        }
        is_payable_bill = classification.is_bill and classification.kind is not None
        if not is_payable_bill:
            state.terminal_reason = "not_a_bill"
            await self._events.step(NOT_A_BILL_STEP, {"reason": classification.reason})
            return _final(summary)
        return _summary(summary)

    async def _extract_invoice(self) -> str:
        state = self._state
        is_ready = (
            state.classification is not None
            and state.classification.kind is not None
            and state.terminal_reason is None
            and state.extraction is None
        )
        if not is_ready:
            return _out_of_order("First classify a document that is a bill.", state)
        try:
            extraction = await self._dependencies.invoice_ingestor.extract_candidate(
                state.owner, state.document, state.classification.kind
            )
        except InvoiceParseError as extraction_error:
            state.terminal_reason = "extraction_failed"
            await self._events.step(
                EXTRACTION_FAILED_STEP,
                {"reason": str(extraction_error), "methods_tried": extraction_error.methods_tried},
            )
            logger.info("payment_run_no_info", run_id=state.run_id)
            return _final({"extracted": False, "methods_tried": extraction_error.methods_tried})
        state.extraction = extraction
        candidate = extraction.candidate
        await self._events.step(
            EXTRACTED_STEP,
            {
                **candidate.model_dump(mode="json"),
                "method": extraction.method,
                "document_origin": (
                    extraction.origin.model_dump(mode="json") if extraction.origin else None
                ),
            },
        )
        return _summary(
            {
                "payee_name": candidate.payee_name,
                "amount": str(candidate.amount) if candidate.amount is not None else None,
                "currency": candidate.currency,
                "invoice_number": candidate.invoice_number,
                "due_date": candidate.due_date.isoformat() if candidate.due_date else None,
                "category": candidate.category,
                "method": extraction.method,
                "origin_country": extraction.origin.country if extraction.origin else None,
                "has_embedded_instructions": bool(candidate.embedded_instructions),
                "embedded_instructions_count": len(candidate.embedded_instructions),
            }
        )

    async def _register_bill(self) -> str:
        state = self._state
        if state.extraction is None or state.claim is not None:
            return _out_of_order("First extract the invoice data.", state)
        owner = state.owner
        candidate = state.extraction.candidate
        policy_client = self._dependencies.policy
        state.policy = await policy_client.get_policy(owner)
        state.match = await policy_client.match_payee(owner.user_id, candidate, state.source.sender)
        currency = _iso_currency(candidate.currency)
        quote = await self._dependencies.fx.quote(currency, datetime.now(UTC).date())
        claim = await self._dependencies.bills.claim_bill(
            owner.user_id, state.source, _bill_fields(candidate, state.match, currency, quote)
        )
        state.claim = claim
        try:
            await self._dependencies.repository.set_run_bill(state.run_id, claim.bill.bill_id)
            claim_payload = _claim_payload(claim)
            await self._events.step(CLAIMED_STEP, claim_payload)
            summary = {
                **claim_payload,
                "payee_known": state.match.payee is not None,
                "amount_usd": claim.bill.amount_usd,
                "fx_source": claim.bill.fx_source,
            }
            if claim.duplicate_of is None:
                return _summary(summary)
            state.decision = await record_duplicate(
                self._dependencies, state.run_id, claim.bill, claim.duplicate_of, state.policy
            )
            await self._record_decided()
            return _final(summary)
        except Exception:
            logger.exception(
                "bill_decision_failed", run_id=state.run_id, bill_id=claim.bill.bill_id
            )
            raise

    async def _evaluate_rules(self) -> str:
        state = self._state
        is_ready = state.claim is not None and state.decision is None and state.evaluation is None
        if not is_ready:
            return _out_of_order("First register the bill.", state)
        try:
            state.context = await build_context(
                self._dependencies,
                state.claim.bill,
                state.source,
                state.extraction.candidate,
                state.match,
                state.policy,
                state.classification,
            )
            state.evaluation = decide(state.context)
        except Exception:
            logger.exception("bill_decision_failed", run_id=state.run_id)
            raise
        flagged_rules = [
            {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "effect": rule.effect,
                "reason": rule.reason,
            }
            for rule in state.evaluation.results
            if rule.effect is not RuleEffect.PASS
        ]
        return _summary(
            {
                "provisional_verdict": state.evaluation.verdict,
                "rules": flagged_rules,
                "passed_count": len(state.evaluation.results) - len(flagged_rules),
            }
        )

    async def _run_checker(self) -> str:
        state = self._state
        is_ready = state.evaluation is not None and state.decision is None and not state.checker_ran
        if not is_ready:
            return _out_of_order("First evaluate the rules.", state)
        if state.evaluation.verdict is not Verdict.PAY:
            return _summary({"skipped": True, "reason": CHECKER_SKIPPED_REASON})
        try:
            state.assessment = await checker.run_checker(
                self._dependencies.llm_gateway, self._dependencies.prompts, state.context
            )
            state.evaluation = checker.apply_checker(
                state.evaluation, state.assessment, state.context
            )
        except Exception:
            logger.exception("bill_decision_failed", run_id=state.run_id)
            raise
        state.checker_ran = True
        answers = state.assessment.answers if state.assessment else []
        return _summary(
            {
                "verdict_after_checker": state.evaluation.verdict,
                "answers": [
                    {"question_id": answer.question_id, "probability": answer.probability}
                    for answer in answers
                ],
            }
        )

    async def _settle_decision(self) -> str:
        state = self._state
        if state.evaluation is None or state.decision is not None:
            return _out_of_order("First evaluate the rules.", state)
        needs_checker = state.evaluation.verdict is Verdict.PAY and not state.checker_ran
        if needs_checker:
            return _out_of_order("Run the second review before paying.", state)
        try:
            state.decision = await settle(
                self._dependencies,
                state.run_id,
                state.claim.bill,
                state.context,
                state.evaluation,
                actor=DecisionActor.AGENT,
                from_status=BillStatus.DECIDING,
                checker=state.assessment,
            )
            await self._record_decided()
        except Exception:
            logger.exception("bill_decision_failed", run_id=state.run_id)
            raise
        return _final(
            {"verdict": state.decision.verdict, "explanation": state.decision.explanation}
        )

    async def _record_decided(self) -> None:
        decision = self._state.decision
        await self._events.step(
            DECIDED_STEP, {"verdict": decision.verdict, "bill_id": str(decision.bill_id)}
        )


def next_step_tool(state: RunState) -> str | None:
    is_finished = state.decision is not None or state.terminal_reason is not None
    if is_finished:
        return None
    if state.classification is None:
        return CLASSIFY_DOCUMENT_TOOL
    if state.extraction is None:
        return EXTRACT_INVOICE_TOOL
    if state.claim is None:
        return REGISTER_BILL_TOOL
    if state.evaluation is None:
        return EVALUATE_RULES_TOOL
    needs_checker = state.evaluation.verdict is Verdict.PAY and not state.checker_ran
    if needs_checker:
        return RUN_CHECKER_TOOL
    return SETTLE_DECISION_TOOL


def _summary(summary: dict) -> str:
    return json.dumps(summary, ensure_ascii=False, default=str)


def _final(summary: dict) -> str:
    return _summary({**summary, "final": True})


def _out_of_order(hint: str, state: RunState) -> str:
    return _summary({"error": hint, "next_tool": next_step_tool(state)})


def _bill_fields(
    candidate: PaymentCandidateBase,
    match: PayeeMatch,
    currency: str | None,
    quote: FxQuote | None,
) -> BillFields:
    is_convertible = quote is not None and candidate.amount is not None
    return BillFields(
        kind=candidate.kind,
        payee_id=match.payee.payee_id if match.payee else None,
        payee_name=candidate.payee_name,
        normalized_payee_name=match.normalized_payee_name,
        invoice_number=candidate.invoice_number,
        amount=candidate.amount,
        currency=currency,
        amount_usd=quote.convert(candidate.amount) if is_convertible else None,
        fx_usd_per_unit=quote.usd_per_unit if quote else None,
        fx_rate_date=quote.rate_date if quote else None,
        fx_source=quote.source if quote else None,
        category=candidate.category,
        due_date=candidate.due_date,
        candidate=candidate.model_dump(mode="json"),
    )


def _iso_currency(currency: str | None) -> str | None:
    normalized_currency = (currency or "").strip().upper()
    return normalized_currency if ISO_CURRENCY_CODE.fullmatch(normalized_currency) else None


def _claim_payload(claim: BillClaim) -> dict:
    return {
        "bill_id": str(claim.bill.bill_id),
        "duplicate_of": str(claim.duplicate_of.bill_id) if claim.duplicate_of else None,
    }
