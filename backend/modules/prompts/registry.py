from modules.prompts.base import Prompt
from modules.prompts.bill_classification import BillClassificationPrompt
from modules.prompts.candidate_extraction import (
    CompanyExtractionPrompt,
    PersonExtractionPrompt,
    ServiceExtractionPrompt,
)
from modules.prompts.email_triage import EmailTriagePrompt
from modules.prompts.hello_world import HelloWorldPrompt
from modules.prompts.main_agent import MainAgentPrompt
from modules.prompts.payment_checker import PaymentCheckerPrompt

PROMPTS: tuple[Prompt, ...] = (
    MainAgentPrompt(),
    BillClassificationPrompt(),
    ServiceExtractionPrompt(),
    PersonExtractionPrompt(),
    CompanyExtractionPrompt(),
    PaymentCheckerPrompt(),
    EmailTriagePrompt(),
    HelloWorldPrompt(),
)
