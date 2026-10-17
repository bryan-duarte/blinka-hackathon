import base64
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.files import FileParseStatus
from contracts.invoices import InvoiceData, InvoiceParseResult
from contracts.prompts import PromptId
from core.agents import MessageContent
from core.logging_config import get_logger
from modules.invoice_ingestor.errors import InvoiceParseError
from modules.invoice_ingestor.repository import InvoicesRepository

if TYPE_CHECKING:
    from clients.files import FilesClient
    from clients.llm import LlmGatewayClient
    from clients.prompts import PromptsClient

logger = get_logger(__name__)

PDF_MIME = "application/pdf"
PDF_EXTRACTION_INSTRUCTION = "Extract the invoice data from this PDF."
PDF_UPLOAD_FILENAME = "invoice.pdf"


class InvoiceIngestorService:
    def __init__(
        self,
        files: "FilesClient",
        llm: "LlmGatewayClient",
        prompts: "PromptsClient",
        repository: InvoicesRepository,
    ) -> None:
        self._files = files
        self._llm = llm
        self._prompts = prompts
        self._repository = repository

    async def parse(self, owner: CurrentUser, file_id: UUID) -> InvoiceParseResult:
        await self._files.get(owner, file_id)
        cached_invoice = await self._repository.get(file_id)
        if cached_invoice is not None:
            return InvoiceParseResult(file_id=file_id, invoice=cached_invoice)
        file_content = await self._files.read_bytes(owner, file_id)
        try:
            invoice = await self._extract_invoice(file_content.file.mime, file_content.content)
        except Exception as extraction_error:
            logger.exception("invoice_parse_failed", file_id=file_id)
            raise InvoiceParseError from extraction_error
        await self._repository.upsert(file_id, invoice)
        await self._files.set_parse_status(file_id, FileParseStatus.PARSED)
        return InvoiceParseResult(file_id=file_id, invoice=invoice)

    async def _extract_invoice(self, mime: str, content: bytes) -> InvoiceData:
        return await self._llm.extract(
            model_kind="main",
            system=self._prompts.get_text_prompt(PromptId.INVOICE_EXTRACTION),
            user_content=_build_user_content(mime, content),
            schema=InvoiceData,
        )


def _build_user_content(mime: str, content: bytes) -> MessageContent:
    if mime != PDF_MIME:
        return content.decode("utf-8", errors="replace")
    encoded_pdf = base64.b64encode(content).decode()
    return [
        {"type": "text", "text": PDF_EXTRACTION_INSTRUCTION},
        {
            "type": "file",
            "base64": encoded_pdf,
            "mime_type": PDF_MIME,
            "filename": PDF_UPLOAD_FILENAME,
        },
    ]
