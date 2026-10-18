from modules.prompts.base import Prompt
from modules.prompts.bill_classification import BillClassificationPrompt
from modules.prompts.candidate_extraction import (
    CompanyExtractionPrompt,
    PersonExtractionPrompt,
    ServiceExtractionPrompt,
)
from modules.prompts.email_triage import EmailTriagePrompt
from modules.prompts.payment_checker import PaymentCheckerPrompt
from modules.prompts.payments_agent import PaymentsAgentPrompt

PROMPTS: tuple[Prompt, ...] = (
    PaymentsAgentPrompt(),
    BillClassificationPrompt(),
    ServiceExtractionPrompt(),
    PersonExtractionPrompt(),
    CompanyExtractionPrompt(),
    PaymentCheckerPrompt(),
    EmailTriagePrompt(),
)
