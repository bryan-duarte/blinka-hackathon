import base64
from typing import TYPE_CHECKING

from contracts.auth import CurrentUser
from contracts.bills import BillDocument
from contracts.files import PDF_MIME, XML_MIMES, FileParseStatus, StoredFileContent
from contracts.llm import ModelKind
from contracts.payment_candidates import (
    CANDIDATE_SCHEMAS,
    BillClassification,
    CandidateExtraction,
    DocumentFields,
    ExpenseReading,
    ExtractionMethod,
)
from contracts.payment_policy import PayeeKind
from contracts.prompts import PromptId
from core.agents import MessageContent
from core.logging_config import get_logger
from modules.document_vision import DocumentVisionError
from modules.invoice_ingestor.candidates import (
    candidate_from_document,
    has_payee_and_amount,
    overlay_document,
)
from modules.invoice_ingestor.errors import BillClassificationError, InvoiceParseError
from modules.invoice_ingestor.origin import resolve_countries
from modules.invoice_ingestor.xml_parser import parse_invoice_xml

if TYPE_CHECKING:
    from clients.document_vision import DocumentVisionClient
    from clients.files import FilesClient
    from clients.llm import LlmGatewayClient
    from clients.prompts import PromptsClient

logger = get_logger(__name__)

PDF_ATTACHMENT_NOTE = "The attached PDF is the bill document."
UNSCREENED_PDF_NOTE = (
    "A PDF bill is attached but it has no text layer; it is withheld from you here. "
    "Judge from the sender and the email body."
)
FALLBACK_TEXT_ENCODING = "latin-1"
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
        document_vision: "DocumentVisionClient",
    ) -> None:
        self._files = files
        self._llm = llm
        self._prompts = prompts
        self._document_vision = document_vision

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
    ) -> CandidateExtraction:
        attachment = await self._attachment(owner, document)
        if attachment is None:
            extraction = await self._extract_with_llm(
                kind, _build_user_content(document, None), ExtractionMethod.EMAIL_LLM
            )
        elif attachment.file.mime in XML_MIMES:
            extraction = await self._extract_from_xml(kind, document, attachment)
        elif attachment.file.mime == PDF_MIME:
            extraction = await self._extract_from_pdf(owner, kind, document, attachment)
        else:
            extraction = await self._extract_with_llm(
                kind, _build_user_content(document, attachment), ExtractionMethod.EMAIL_LLM
            )
        resolved_candidate = resolve_countries(extraction.candidate, extraction.origin)
        return extraction.model_copy(update={"candidate": resolved_candidate})

    async def _extract_from_xml(
        self, kind: PayeeKind, document: BillDocument, attachment: StoredFileContent
    ) -> CandidateExtraction:
        parsed_invoice = parse_invoice_xml(attachment.content)
        xml_fields = parsed_invoice.fields if parsed_invoice else DocumentFields()
        origin = parsed_invoice.origin if parsed_invoice else None
        llm_extraction = await self._try_llm(
            kind, _build_user_content(document, attachment), ExtractionMethod.XML_LLM
        )
        method = ExtractionMethod.XML if xml_fields.is_sufficient else ExtractionMethod.XML_LLM
        extraction = _overlaid(kind, llm_extraction, xml_fields, method).model_copy(
            update={"origin": origin}
        )
        logger.info(
            "xml_invoice_read",
            file_id=attachment.file.file_id,
            method=method,
            origin_country=origin.country if origin else None,
        )
        is_unreadable = method is ExtractionMethod.XML_LLM and (
            llm_extraction is None or not has_payee_and_amount(extraction.candidate)
        )
        if is_unreadable:
            raise InvoiceParseError(
                "no extraction method found payee and amount",
                (ExtractionMethod.XML, ExtractionMethod.XML_LLM),
            )
        return extraction

    async def _extract_from_pdf(
        self,
        owner: CurrentUser,
        kind: PayeeKind,
        document: BillDocument,
        attachment: StoredFileContent,
    ) -> CandidateExtraction:
        methods_tried = [ExtractionMethod.TEXTRACT]
        reading = await self._read_expense(attachment)
        visual_fields = reading.fields if reading else DocumentFields()
        pdf_text = await self._pdf_text(owner, attachment, reading)
        text_extraction = None
        if pdf_text:
            methods_tried.append(ExtractionMethod.PDF_TEXT_LLM)
            text_extraction = await self._try_llm(
                kind, _build_text_content(document, pdf_text), ExtractionMethod.PDF_TEXT_LLM
            )
        if visual_fields.is_sufficient:
            return _overlaid(kind, text_extraction, visual_fields, ExtractionMethod.TEXTRACT)
        if text_extraction and has_payee_and_amount(text_extraction.candidate):
            return _overlaid(kind, text_extraction, visual_fields, ExtractionMethod.PDF_TEXT_LLM)
        methods_tried.append(ExtractionMethod.PDF_FILE_LLM)
        file_extraction = await self._try_llm(
            kind, _build_pdf_content(document, attachment), ExtractionMethod.PDF_FILE_LLM
        )
        if file_extraction and has_payee_and_amount(file_extraction.candidate):
            return _overlaid(kind, file_extraction, visual_fields, ExtractionMethod.PDF_FILE_LLM)
        raise InvoiceParseError("no extraction method found payee and amount", tuple(methods_tried))

    async def _read_expense(self, attachment: StoredFileContent) -> ExpenseReading | None:
        try:
            return await self._document_vision.read_expense(attachment.content)
        except DocumentVisionError as vision_error:
            logger.info(
                "visual_extraction_failed",
                file_id=attachment.file.file_id,
                reason=str(vision_error),
            )
            return None

    async def _pdf_text(
        self, owner: CurrentUser, attachment: StoredFileContent, reading: ExpenseReading | None
    ) -> str | None:
        if attachment.file.parse_status is FileParseStatus.PARSED:
            return await self._files.get_context(owner, [attachment.file.file_id])
        return reading.text if reading else None

    async def _try_llm(
        self, kind: PayeeKind, user_content: MessageContent, method: ExtractionMethod
    ) -> CandidateExtraction | None:
        try:
            return await self._extract_with_llm(kind, user_content, method)
        except InvoiceParseError:
            return None

    async def _extract_with_llm(
        self, kind: PayeeKind, user_content: MessageContent, method: ExtractionMethod
    ) -> CandidateExtraction:
        try:
            candidate = await self._llm.extract(
                model_kind=READING_MODEL_KIND,
                system=self._prompts.get_text_prompt(EXTRACTION_PROMPTS[kind]),
                user_content=user_content,
                schema=CANDIDATE_SCHEMAS[kind],
            )
        except Exception as extraction_error:
            logger.exception("candidate_extraction_failed", kind=kind, method=method)
            raise InvoiceParseError(
                "language model extraction failed", (method,)
            ) from extraction_error
        return CandidateExtraction(candidate=candidate, method=method)

    async def _attachment(
        self, owner: CurrentUser, document: BillDocument
    ) -> StoredFileContent | None:
        if document.file_id is None:
            return None
        return await self._files.read_bytes(owner, document.file_id)

    async def _user_content(self, owner: CurrentUser, document: BillDocument) -> MessageContent:
        return _build_user_content(document, await self._attachment(owner, document))


def _overlaid(
    kind: PayeeKind,
    llm_extraction: CandidateExtraction | None,
    structured_fields: DocumentFields,
    method: ExtractionMethod,
) -> CandidateExtraction:
    if llm_extraction is None:
        candidate = candidate_from_document(kind, structured_fields)
    else:
        candidate = overlay_document(llm_extraction.candidate, structured_fields)
    return CandidateExtraction(candidate=candidate, method=method)


def _envelope_blocks(document: BillDocument) -> list[str | dict]:
    envelope = (
        f"<sender>{document.sender}</sender>\n<email_body>\n{document.body_text}\n</email_body>"
    )
    return [{"type": "text", "text": envelope}]


def _build_text_content(document: BillDocument, attachment_text: str) -> MessageContent:
    return [
        *_envelope_blocks(document),
        {"type": "text", "text": f"<attachment>\n{attachment_text}\n</attachment>"},
    ]


def _build_pdf_content(document: BillDocument, attachment: StoredFileContent) -> MessageContent:
    encoded_pdf = base64.b64encode(attachment.content).decode()
    return [
        *_envelope_blocks(document),
        {"type": "text", "text": PDF_ATTACHMENT_NOTE},
        {
            "type": "file",
            "base64": encoded_pdf,
            "mime_type": PDF_MIME,
            "filename": attachment.file.filename,
        },
    ]


def _build_user_content(
    document: BillDocument, attachment: StoredFileContent | None
) -> MessageContent:
    if attachment is None:
        return _envelope_blocks(document)
    is_unscreened_pdf = (
        attachment.file.mime == PDF_MIME
        and attachment.file.parse_status is not FileParseStatus.PARSED
    )
    if is_unscreened_pdf:
        return [*_envelope_blocks(document), {"type": "text", "text": UNSCREENED_PDF_NOTE}]
    if attachment.file.mime == PDF_MIME:
        return _build_pdf_content(document, attachment)
    return _build_text_content(document, _decode_attachment_text(attachment.content))


def _decode_attachment_text(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode(FALLBACK_TEXT_ENCODING)
