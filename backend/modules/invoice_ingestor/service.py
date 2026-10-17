import base64
from typing import TYPE_CHECKING

from contracts.auth import CurrentUser
from contracts.bills import BillDocument
from contracts.files import StoredFileContent
from contracts.llm import ModelKind
from contracts.payment_candidates import (
    CANDIDATE_SCHEMAS,
    BillClassification,
    PaymentCandidateBase,
)
from contracts.payment_policy import PayeeKind
from contracts.prompts import PromptId
from core.agents import MessageContent
from core.logging_config import get_logger
from modules.invoice_ingestor.errors import BillClassificationError, InvoiceParseError

if TYPE_CHECKING:
    from clients.files import FilesClient
    from clients.llm import LlmGatewayClient
    from clients.prompts import PromptsClient

logger = get_logger(__name__)

PDF_MIME = "application/pdf"
PDF_ATTACHMENT_NOTE = "The attached PDF is the bill document."
READING_MODEL_KIND: ModelKind = "main"
EXTRACTION_PROMPTS: dict[PayeeKind, PromptId] = {
    PayeeKind.SERVICE: PromptId.SERVICE_EXTRACTION,
    PayeeKind.PERSON: PromptId.PERSON_EXTRACTION,
    PayeeKind.COMPANY: PromptId.COMPANY_EXTRACTION,
}


class InvoiceIngestorService:
    def __init__(
        self,
        files: "FilesClient",
        llm: "LlmGatewayClient",
        prompts: "PromptsClient",
    ) -> None:
        self._files = files
        self._llm = llm
        self._prompts = prompts

    async def classify(self, owner: CurrentUser, document: BillDocument) -> BillClassification:
        user_content = await self._user_content(owner, document)
        try:
            return await self._llm.extract(
                model_kind=READING_MODEL_KIND,
                system=self._prompts.get_text_prompt(PromptId.BILL_CLASSIFICATION),
                user_content=user_content,
                schema=BillClassification,
            )
        except Exception as classification_error:
            logger.exception("bill_classification_failed", file_id=document.file_id)
            raise BillClassificationError from classification_error

    async def extract_candidate(
        self, owner: CurrentUser, document: BillDocument, kind: PayeeKind
    ) -> PaymentCandidateBase:
        user_content = await self._user_content(owner, document)
        try:
            return await self._llm.extract(
                model_kind=READING_MODEL_KIND,
                system=self._prompts.get_text_prompt(EXTRACTION_PROMPTS[kind]),
                user_content=user_content,
                schema=CANDIDATE_SCHEMAS[kind],
            )
        except Exception as extraction_error:
            logger.exception("candidate_extraction_failed", kind=kind, file_id=document.file_id)
            raise InvoiceParseError from extraction_error

    async def _user_content(self, owner: CurrentUser, document: BillDocument) -> MessageContent:
        attachment = None
        if document.file_id is not None:
            attachment = await self._files.read_bytes(owner, document.file_id)
        return _build_user_content(document, attachment)


def _build_user_content(
    document: BillDocument, attachment: StoredFileContent | None
) -> MessageContent:
    envelope = (
        f"<sender>{document.sender}</sender>\n<email_body>\n{document.body_text}\n</email_body>"
    )
    blocks: list[str | dict] = [{"type": "text", "text": envelope}]
    if attachment is None:
        return blocks
    if attachment.file.mime == PDF_MIME:
        encoded_pdf = base64.b64encode(attachment.content).decode()
        blocks.append({"type": "text", "text": PDF_ATTACHMENT_NOTE})
        blocks.append(
            {
                "type": "file",
                "base64": encoded_pdf,
                "mime_type": PDF_MIME,
                "filename": attachment.file.filename,
            }
        )
        return blocks
    attachment_text = attachment.content.decode("utf-8", errors="replace")
    blocks.append({"type": "text", "text": f"<attachment>\n{attachment_text}\n</attachment>"})
    return blocks
