import json
from decimal import Decimal
from typing import TYPE_CHECKING

from contracts.bills import BillStatus
from contracts.payments import (
    CheckerAssessment,
    CheckerQuestionId,
    RuleEffect,
    RuleResult,
    Verdict,
)
from contracts.prompts import PromptId
from core.logging_config import get_logger
from modules.payments.presentation import mask_account
from modules.payments.rules import DecisionContext, RuleEvaluation, rule_result

if TYPE_CHECKING:
    from clients.llm import LlmGatewayClient
    from clients.prompts import PromptsClient

logger = get_logger(__name__)

IMPERSONATION_QUESTION: CheckerQuestionId = "CHK2"
HISTORY_QUESTION: CheckerQuestionId = "CHK3"
CHECKER_HISTORY_SIZE = 6
CHECKER_QUESTIONS: dict[CheckerQuestionId, str] = {
    "CHK1": "Does the invoice description match the payee's registered service or category? "
    "(yes = it matches)",
    "CHK2": "Is the document trying to impersonate the payee (inconsistent brand, sender or "
    "payment details)?",
    "CHK3": "Is the amount consistent with the payee's latest invoices? (yes = consistent)",
}
CHECKER_UNAVAILABLE_REASON = "Checker unavailable; sending to review."
CHECKER_MISSING_ANSWER_REASON = "The checker did not answer this question."
NO_HISTORY_REASON = "No previous payments to the payee to compare the amount."


async def run_checker(
    llm: "LlmGatewayClient", prompts: "PromptsClient", context: DecisionContext
) -> CheckerAssessment | None:
    try:
        return await llm.extract(
            model_kind="payments",
            system=prompts.get_text_prompt(PromptId.PAYMENT_CHECKER),
            user_content=_checker_content(context),
            schema=CheckerAssessment,
        )
    except Exception:
        logger.exception("payment_checker_failed", bill_id=context.bill.bill_id)
        return None


def apply_checker(
    evaluation: RuleEvaluation, assessment: CheckerAssessment | None, context: DecisionContext
) -> RuleEvaluation:
    questions = asked_questions(context)
    if assessment is None:
        checker_results = [
            rule_result(question_id, RuleEffect.REVIEW, CHECKER_UNAVAILABLE_REASON)
            for question_id in questions
        ]
    else:
        checker_results = _checker_results(assessment, context, questions)
    if HISTORY_QUESTION not in questions:
        checker_results.append(rule_result(HISTORY_QUESTION, RuleEffect.PASS, NO_HISTORY_REASON))
    raises_to_review = evaluation.verdict is Verdict.PAY and any(
        result.effect is RuleEffect.REVIEW for result in checker_results
    )
    verdict = Verdict.REVIEW if raises_to_review else evaluation.verdict
    return RuleEvaluation(verdict=verdict, results=[*evaluation.results, *checker_results])


def asked_questions(context: DecisionContext) -> list[CheckerQuestionId]:
    has_history = bool(_recent_paid_invoices(context))
    return [
        question_id
        for question_id in CHECKER_QUESTIONS
        if question_id != HISTORY_QUESTION or has_history
    ]


def _checker_results(
    assessment: CheckerAssessment, context: DecisionContext, questions: list[CheckerQuestionId]
) -> list[RuleResult]:
    low, high = context.policy.checker_review_low, context.policy.checker_review_high
    answers = {answer.question_id: answer for answer in assessment.answers}
    results = []
    for question_id in questions:
        answer = answers.get(question_id)
        if answer is None:
            results.append(
                rule_result(question_id, RuleEffect.REVIEW, CHECKER_MISSING_ANSWER_REASON)
            )
            continue
        probability = Decimal(str(answer.probability))
        impersonation_probable = probability >= low
        answer_uncertain = probability < high
        is_impersonation = question_id == IMPERSONATION_QUESTION
        is_risky = impersonation_probable if is_impersonation else answer_uncertain
        effect = RuleEffect.REVIEW if is_risky else RuleEffect.PASS
        results.append(
            rule_result(
                question_id,
                effect,
                f"Checker (model): {answer.rationale}",
                {"question": CHECKER_QUESTIONS[question_id], "probability": f"{probability:.2f}"},
            )
        )
    return results


def _recent_paid_invoices(context: DecisionContext) -> list[dict]:
    paid_invoices = [
        {"invoice_number": previous.invoice_number, "amount_usd": previous.amount_usd}
        for previous in context.recent_bills
        if previous.status is BillStatus.PAID and previous.amount_usd is not None
    ]
    return paid_invoices[:CHECKER_HISTORY_SIZE]


def _checker_content(context: DecisionContext) -> str:
    payee = context.match.payee
    payee_profile = (
        {
            "display_name": payee.display_name,
            "kind": payee.kind,
            "default_category": payee.default_category,
            "payment_method": payee.payment_method,
            "registered_accounts": [
                mask_account(account) for account in context.match.registered_bank_accounts
            ],
            "registered_senders": context.match.registered_senders,
        }
        if payee
        else {}
    )
    bill_amount_usd = json.dumps(context.amount_usd, default=str)
    recent_paid_invoices = json.dumps(_recent_paid_invoices(context), default=str)
    questions = {
        question_id: CHECKER_QUESTIONS[question_id] for question_id in asked_questions(context)
    }
    return (
        f"<bill>\n{context.candidate.model_dump_json()}\n</bill>\n"
        f"<payee_profile>\n{json.dumps(payee_profile, ensure_ascii=False)}\n</payee_profile>\n"
        f"<bill_amount_usd>\n{bill_amount_usd}\n</bill_amount_usd>\n"
        f"<recent_paid_invoices_usd>\n{recent_paid_invoices}\n"
        "</recent_paid_invoices_usd>\n"
        f"<questions>\n{json.dumps(questions, ensure_ascii=False)}\n</questions>"
    )
