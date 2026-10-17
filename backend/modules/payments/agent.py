from deepagents import create_deep_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from contracts.invoices import InvoiceData

PAYMENTS_AGENT_NAME = "payments"


def build_invoice_context_tool(invoice: InvoiceData) -> BaseTool:
    @tool
    async def get_invoice_context() -> str:
        """Return the invoice data for this payment run as JSON."""
        return invoice.model_dump_json()

    return get_invoice_context


@tool
async def execute_payment(amount: float, currency: str, vendor: str) -> dict:
    """Execute the invoice payment. Returns the payment confirmation."""
    return {
        "executed": True,
        "amount": amount,
        "currency": currency,
        "vendor": vendor,
    }


def build_payment_agent(
    llm: BaseChatModel,
    payments_checkpointer: BaseCheckpointSaver | None,
    invoice: InvoiceData,
    system_prompt: str,
) -> CompiledStateGraph:
    tools = [build_invoice_context_tool(invoice), execute_payment]
    return create_deep_agent(
        model=llm,
        system_prompt=system_prompt,
        tools=tools,
        checkpointer=payments_checkpointer,
    )
