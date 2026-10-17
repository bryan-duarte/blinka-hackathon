import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest

from contracts.auth import CurrentUser
from contracts.bills import BillDocument
from contracts.files import (
    PDF_MIME,
    XML_MIME,
    EvidenceIntakeStatus,
    EvidenceRole,
    FileParseStatus,
    FileScanStatus,
    FileUploadResult,
    StoredFile,
    StoredFileContent,
    UploadedContent,
)
from contracts.payment_candidates import (
    DocumentFields,
    DocumentIssuer,
    DocumentOrigin,
    ExpenseReading,
    ExtractionMethod,
    FieldEvidence,
    PaymentCandidateBase,
)
from contracts.payment_policy import PayeeKind
from core.config import StorageSettings
from modules.document_vision import DocumentVisionError
from modules.document_vision.textract import _best_fields_by_type, _document_fields
from modules.files import evidence
from modules.files.archives import MAX_ARCHIVE_ENTRIES, expand_zip
from modules.files.errors import UnsafeArchiveError
from modules.files.scan import SCAN_STATUS_TAG_KEY, MalwareScanService
from modules.invoice_ingestor.candidates import candidate_from_document
from modules.invoice_ingestor.errors import InvoiceParseError
from modules.invoice_ingestor.origin import resolve_countries
from modules.invoice_ingestor.service import InvoiceIngestorService

XML_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "xml"
OWNER = CurrentUser(user_id=uuid4(), email="finance@blinka.test")


def _zip(members: dict[str, bytes], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _uploaded(
    mime: str, scan_status: FileScanStatus = FileScanStatus.CLEAN, content: bytes = b"x"
) -> UploadedContent:
    upload = FileUploadResult(
        file_id=uuid4(),
        filename="file",
        mime=mime,
        size_bytes=len(content),
        parse_status=FileParseStatus.PARSED,
        scan_status=scan_status,
    )
    return UploadedContent(upload=upload, content=content)


def test_expand_zip_keeps_only_supported_members_by_basename() -> None:
    archive = _zip(
        {
            "../../etc/factura.xml": b"<x/>",
            "docs/factura.pdf": b"%PDF-1.4",
            "__MACOSX/._factura.pdf": b"junk",
            ".hidden.xml": b"<x/>",
            "notes.txt": b"ignored",
        }
    )

    members = expand_zip(archive)

    assert [(member.filename, member.mime) for member in members] == [
        ("factura.xml", XML_MIME),
        ("factura.pdf", PDF_MIME),
    ]


@pytest.mark.parametrize(
    "archive",
    [
        _zip({f"f{index}.pdf": b"%PDF" for index in range(MAX_ARCHIVE_ENTRIES + 1)}),
        _zip({"bomb.xml": b"0" * 1_000_000}),
        _zip({"notes.txt": b"no invoices here"}),
        b"PK\x03\x04 not really a zip",
    ],
    ids=["too-many-entries", "compression-ratio", "no-supported-members", "corrupt"],
)
def test_expand_zip_rejects_unsafe_archives(archive: bytes) -> None:
    with pytest.raises(UnsafeArchiveError):
        expand_zip(archive)


def test_ready_intake_prefers_xml_and_assigns_roles() -> None:
    archive = _uploaded("application/zip")
    pdf = _uploaded(PDF_MIME)
    xml = _uploaded(XML_MIME, content=b"<invoice/>")

    intake = evidence.ready_intake([archive], [pdf, xml])

    assert intake.status is EvidenceIntakeStatus.READY
    assert intake.primary_file_id == xml.upload.file_id
    assert [(link.file_id, link.role) for link in intake.evidence] == [
        (xml.upload.file_id, EvidenceRole.PRIMARY),
        (pdf.upload.file_id, EvidenceRole.SECONDARY),
        (archive.upload.file_id, EvidenceRole.ARCHIVE),
    ]


def test_quarantined_upload_is_detected() -> None:
    infected = _uploaded(PDF_MIME, FileScanStatus.THREAT)

    assert evidence.first_quarantined([_uploaded(XML_MIME), infected]) is infected
    assert evidence.first_quarantined([_uploaded(PDF_MIME, FileScanStatus.UNSUPPORTED)]) is None


class _TaggedStorage:
    def __init__(self, tag_values: list[str | None]) -> None:
        self._tag_values = tag_values
        self.polls = 0

    async def object_tags(self, key: str) -> dict[str, str]:
        tag_value = self._tag_values[min(self.polls, len(self._tag_values) - 1)]
        self.polls += 1
        return {SCAN_STATUS_TAG_KEY: tag_value} if tag_value else {}


def _scan_settings(**changes: object) -> StorageSettings:
    return StorageSettings(scan_timeout_seconds=0.05, scan_poll_interval_seconds=0.01, **changes)


@pytest.mark.parametrize(
    ("tag_values", "expected_status"),
    [
        ([None, "NO_THREATS_FOUND"], FileScanStatus.CLEAN),
        (["THREATS_FOUND"], FileScanStatus.THREAT),
        (["UNSUPPORTED"], FileScanStatus.UNSUPPORTED),
        (["ACCESS_DENIED"], FileScanStatus.FAILED),
        ([None], FileScanStatus.FAILED),
    ],
)
async def test_wait_for_scan_maps_guardduty_tags(
    tag_values: list[str | None], expected_status: FileScanStatus
) -> None:
    scanner = MalwareScanService(_TaggedStorage(tag_values), _scan_settings())

    assert await scanner.wait_for_scan("key") is expected_status


async def test_wait_for_scan_disabled_skips_polling() -> None:
    storage = _TaggedStorage([None])
    scanner = MalwareScanService(storage, _scan_settings(malware_scan_enabled=False))

    assert await scanner.wait_for_scan("key") is FileScanStatus.DISABLED
    assert storage.polls == 0


def test_textract_summary_fields_map_to_document_fields() -> None:
    expense_document = {
        "SummaryFields": [
            {
                "Type": {"Text": "VENDOR_NAME"},
                "ValueDetection": {"Text": "Nova Ltda", "Confidence": 80},
            },
            {
                "Type": {"Text": "VENDOR_NAME"},
                "ValueDetection": {"Text": "NOVA LTDA.", "Confidence": 99},
            },
            {
                "Type": {"Text": "TOTAL"},
                "ValueDetection": {"Text": "$1.234,50", "Confidence": 95},
                "Currency": {"Code": "USD"},
            },
            {
                "Type": {"Text": "INVOICE_RECEIPT_ID"},
                "ValueDetection": {"Text": "F-77", "Confidence": 90},
            },
        ]
    }

    fields = _document_fields(_best_fields_by_type(expense_document))

    assert fields.payee_name == "NOVA LTDA."
    assert fields.amount == Decimal("1234.50")
    assert fields.currency == "USD"
    assert fields.invoice_number == "F-77"
    assert fields.is_sufficient


class _FakeFiles:
    def __init__(self, stored_content: StoredFileContent) -> None:
        self._stored_content = stored_content

    async def read_bytes(self, owner: CurrentUser, file_id: object) -> StoredFileContent:
        return self._stored_content

    async def get_context(self, owner: CurrentUser, file_ids: list[object]) -> str:
        return "[file: factura]\nNova Ltda Total USD 120.00"


class _ScriptedLlm:
    def __init__(
        self,
        text_fields: dict[str, object] | None = None,
        file_fields: dict[str, object] | None = None,
    ) -> None:
        self._text_fields = text_fields
        self._file_fields = file_fields
        self.inputs: list[str] = []

    async def extract(self, *, user_content: list, schema: type, **_: object) -> object:
        is_file_input = any(
            isinstance(block, dict) and block.get("type") == "file" for block in user_content
        )
        self.inputs.append("file" if is_file_input else "text")
        candidate_fields = self._file_fields if is_file_input else self._text_fields
        if candidate_fields is None:
            raise RuntimeError("model unavailable")
        empty_candidate = candidate_from_document(
            PayeeKind(schema.model_fields["kind"].default), DocumentFields()
        )
        return empty_candidate.model_copy(update=candidate_fields)


class _Prompts:
    def get_text_prompt(self, prompt_id: object) -> str:
        return "prompt"


class _FakeVision:
    def __init__(self, reading: ExpenseReading | None = None, fails: bool = False) -> None:
        self._reading = reading or ExpenseReading(fields=DocumentFields())
        self._fails = fails
        self.calls = 0

    async def read_expense(self, document: bytes) -> ExpenseReading:
        self.calls += 1
        if self._fails:
            raise DocumentVisionError("UnsupportedDocumentException")
        return self._reading


def _stored(mime: str, content: bytes, parse_status: FileParseStatus) -> StoredFileContent:
    stored_file = StoredFile(
        file_id=uuid4(),
        owner_id=OWNER.user_id,
        filename="factura",
        mime=mime,
        size_bytes=len(content),
        storage_key="key",
        parse_status=parse_status,
        scan_status=FileScanStatus.CLEAN,
        created_at=datetime.now(UTC),
    )
    return StoredFileContent(file=stored_file, content=content)


def _ingestor(
    stored_content: StoredFileContent, vision: _FakeVision, llm: _ScriptedLlm | None = None
) -> InvoiceIngestorService:
    return InvoiceIngestorService(
        _FakeFiles(stored_content), llm or _ScriptedLlm(), _Prompts(), vision
    )


def _document() -> BillDocument:
    return BillDocument(body_text="Factura adjunta", file_id=uuid4(), sender="billing@test")


SUFFICIENT_LLM_FIELDS = {"payee_name": "Nova Ltda", "amount": Decimal("120"), "currency": "USD"}
VISUAL_FIELDS = DocumentFields(
    payee_name="NOVA LTDA.", amount=Decimal("118.50"), tax_id="97.975.000-5"
)


async def test_xml_extraction_is_deterministic_without_llm() -> None:
    xml_content = (XML_FIXTURES_DIR / "dte_cl.xml").read_bytes()
    ingestor = _ingestor(_stored(XML_MIME, xml_content, FileParseStatus.PARSED), _FakeVision())

    extraction = await ingestor.extract_candidate(OWNER, _document(), PayeeKind.COMPANY)

    assert extraction.method is ExtractionMethod.XML
    assert extraction.candidate.payee_name == "Servicios del Sur SpA"
    assert extraction.candidate.amount == Decimal("499800")
    assert extraction.candidate.currency == "CLP"
    assert extraction.candidate.issuer_tax_country == "CL"
    assert extraction.candidate.tax_id == "76543210-K"


async def test_pdf_reads_textract_first_and_llm_only_fills_gaps() -> None:
    vision = _FakeVision(ExpenseReading(fields=VISUAL_FIELDS))
    llm = _ScriptedLlm(text_fields={**SUFFICIENT_LLM_FIELDS, "category": "saas"})
    ingestor = _ingestor(_stored(PDF_MIME, b"%PDF", FileParseStatus.PARSED), vision, llm)

    extraction = await ingestor.extract_candidate(OWNER, _document(), PayeeKind.COMPANY)

    assert vision.calls == 1
    assert extraction.method is ExtractionMethod.TEXTRACT
    assert extraction.candidate.payee_name == "NOVA LTDA."
    assert extraction.candidate.amount == Decimal("118.50")
    assert extraction.candidate.category == "saas"
    assert extraction.candidate.issuer_tax_country == "CL"
    assert llm.inputs == ["text"]


async def test_pdf_falls_back_to_llm_on_textract_ocr_text() -> None:
    vision = _FakeVision(ExpenseReading(fields=DocumentFields(), text="Nova Ltda Total USD 120"))
    llm = _ScriptedLlm(text_fields=SUFFICIENT_LLM_FIELDS)
    ingestor = _ingestor(_stored(PDF_MIME, b"%PDF", FileParseStatus.UNSUPPORTED), vision, llm)

    extraction = await ingestor.extract_candidate(OWNER, _document(), PayeeKind.SERVICE)

    assert extraction.method is ExtractionMethod.PDF_TEXT_LLM
    assert llm.inputs == ["text"]


async def test_pdf_falls_back_to_llm_with_the_pdf_file() -> None:
    llm = _ScriptedLlm(text_fields={"payee_name": "Nova Ltda"}, file_fields=SUFFICIENT_LLM_FIELDS)
    ingestor = _ingestor(
        _stored(PDF_MIME, b"%PDF", FileParseStatus.PARSED), _FakeVision(fails=True), llm
    )

    extraction = await ingestor.extract_candidate(OWNER, _document(), PayeeKind.SERVICE)

    assert extraction.method is ExtractionMethod.PDF_FILE_LLM
    assert extraction.candidate.issuer_tax_country is None
    assert llm.inputs == ["text", "file"]


@pytest.mark.parametrize(
    ("parse_status", "expected_methods"),
    [
        (FileParseStatus.PARSED, ["textract", "pdf_text", "pdf"]),
        (FileParseStatus.FAILED, ["textract", "pdf"]),
    ],
)
async def test_exhausted_pdf_chain_reports_methods_tried(
    parse_status: FileParseStatus, expected_methods: list[str]
) -> None:
    ingestor = _ingestor(_stored(PDF_MIME, b"garbage", parse_status), _FakeVision(fails=True))

    with pytest.raises(InvoiceParseError) as raised:
        await ingestor.extract_candidate(OWNER, _document(), PayeeKind.COMPANY)

    assert raised.value.methods_tried == expected_methods


def _company(**document_fields: object) -> PaymentCandidateBase:
    return candidate_from_document(PayeeKind.COMPANY, DocumentFields(**document_fields))


def _origin(issued_by: DocumentIssuer = DocumentIssuer.SELLER) -> DocumentOrigin:
    return DocumentOrigin(
        country="MX", standard="CFDI", authority="SAT", signal="sat.gob.mx", issued_by=issued_by
    )


@pytest.mark.parametrize(
    ("tax_id", "expected_issuer_tax_country"),
    [
        ("EKU9003173C9", "MX"),
        ("97.975.000-5", "CL"),
        ("76.543.210-K", None),
        ("06.929.383/0001-63", "BR"),
        ("12-3456789", "US"),
        ("DE 123456789", "DE"),
        ("311111111101113", "SA"),
        ("900123456", None),
        ("XEXX010101000", None),
    ],
)
def test_issuer_tax_country_is_inferred_only_from_unambiguous_tax_ids(
    tax_id: str, expected_issuer_tax_country: str | None
) -> None:
    resolved = resolve_countries(_company(tax_id=tax_id), origin=None)

    assert resolved.issuer_tax_country == expected_issuer_tax_country


def test_payee_country_is_never_guessed_from_currency() -> None:
    resolved = resolve_countries(_company(currency="MXN"), origin=None)

    assert resolved.payee_country is None


def test_buyer_issued_documents_keep_issuer_tax_country_empty() -> None:
    candidate = _company(tax_id="EKU9003173C9", issuer_tax_country="CL")

    resolved = resolve_countries(candidate, _origin(DocumentIssuer.BUYER))

    assert resolved.issuer_tax_country is None


def test_tax_id_that_contradicts_the_standard_lowers_confidence() -> None:
    candidate = _company(tax_id="900123456", issuer_tax_country="MX").model_copy(
        update={
            "evidence": [
                FieldEvidence(field="issuer_tax_country", quote="sat.gob.mx", confidence=1.0)
            ]
        }
    )

    resolved = resolve_countries(candidate, _origin())

    issuer_evidence = [item for item in resolved.evidence if item.field == "issuer_tax_country"]
    assert resolved.issuer_tax_country == "MX"
    assert [item.confidence for item in issuer_evidence] == [0.5]


@pytest.mark.parametrize(
    ("bank_account", "expected_country"),
    [
        ("DE79 0000 0000 1234 5678 90", "DE"),
        ("NL57 RABO 0107 3075 10", "NL"),
        ("002010077777777771", "MX"),
        ("BCHICLRM", "CL"),
        ("CL-001-2233445566", None),
        ("DE79 0000 0000 1234 5678 91", None),
    ],
)
def test_bank_account_country(bank_account: str, expected_country: str | None) -> None:
    candidate = _company().model_copy(update={"bank_account": bank_account})

    assert resolve_countries(candidate, origin=None).bank_account_country == expected_country


def test_scan_failure_is_reported_apart_from_threats() -> None:
    timed_out = _uploaded(PDF_MIME, FileScanStatus.FAILED)
    infected = _uploaded(PDF_MIME, FileScanStatus.THREAT)

    assert evidence.quarantined_intake(timed_out).status is EvidenceIntakeStatus.SCAN_FAILED
    assert evidence.quarantined_intake(infected).status is EvidenceIntakeStatus.MALWARE


def test_non_invoice_document_is_primary_as_last_resort() -> None:
    text_bill = _uploaded("text/plain")

    intake = evidence.ready_intake([], [text_bill])

    assert intake.status is EvidenceIntakeStatus.READY
    assert intake.primary_file_id == text_bill.upload.file_id
