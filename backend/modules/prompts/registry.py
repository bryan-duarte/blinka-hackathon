from modules.prompts.base import Prompt
from modules.prompts.email_triage import EmailTriagePrompt
from modules.prompts.hello_world import HelloWorldPrompt
from modules.prompts.invoice_extraction import InvoiceExtractionPrompt
from modules.prompts.main_agent import MainAgentPrompt
from modules.prompts.payment_agent import PaymentAgentPrompt

PROMPTS: tuple[Prompt, ...] = (
    MainAgentPrompt(),
    PaymentAgentPrompt(),
    InvoiceExtractionPrompt(),
    EmailTriagePrompt(),
    HelloWorldPrompt(),
)
