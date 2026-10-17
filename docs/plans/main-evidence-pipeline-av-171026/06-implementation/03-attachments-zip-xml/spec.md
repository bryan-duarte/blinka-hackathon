# Attachments — ZIP/XML intake, safe expansion, primary-source selection

## Overview

Teach both intake paths (email webhook via Composio, console upload) to accept ZIP and XML attachments, expand ZIPs safely, store every file as evidence, and pick the extraction source with XML preferred over PDF.

## Files to Modify/Create

- `backend/modules/mail_gateway/gmail.py` — `first_pdf_attachment` → `select_attachments(payload)` returning all `.pdf/.zip/.xml` entries with mime guessed from filename
- `backend/modules/mail_gateway/service.py` — `_fetch_gmail`/`_fetch_outlook` use the new selector; `_sized_attachment` stops hardcoding `mime="application/pdf"` (:298), enforces the 10 MB cap per attachment (unchanged)
- `backend/modules/files/archives.py` (new) — `expand_zip()`, `UnsafeArchiveError`
- `backend/modules/files/errors.py` — add `UnsafeArchiveError` if the module has no errors file (create it)
- `backend/api/routers/files.py` — `POST /files` accepts `application/zip`, `application/xml`, `text/xml` (validate magic bytes: `PK\x03\x04` for zip)
- `backend/modules/inbox/pipeline.py` — `_store_attachment` → `_store_attachments` (multi-file, expansion, roles, scan-aware blocking)
- `backend/modules/payments/service.py` — `start_file_run` (:103): zip/xml expansion + same selection for uploads

## Implementation Guidelines

`select_attachments` policy (both providers): return every attachment whose filename extension ∈ {`.pdf`, `.zip`, `.xml`}; mime = `mimetypes.guess_type(filename)` with a static fallback map (`zip→application/zip`, `xml→application/xml`). No ordering assumptions.

`expand_zip` (bomb/path-hardened, orientative):

```python
MAX_ENTRIES, MAX_TOTAL_BYTES, MAX_RATIO = 20, 50 * 1024 * 1024, 100
ALLOWED_MEMBER_EXTS = {".pdf", ".xml"}

def expand_zip(data: bytes) -> list[tuple[str, bytes, str]]:
    out, total = [], 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        infos = [i for i in zf.infolist()
                 if not i.is_dir() and not i.filename.startswith(("__MACOSX/", ".", "/"))]
        if len(infos) > MAX_ENTRIES: raise UnsafeArchiveError("too many entries")
        for info in infos:
            name = os.path.basename(info.filename)                 # path traversal guard
            ext = os.path.splitext(name)[1].lower()
            if ext not in ALLOWED_MEMBER_EXTS: continue
            if info.file_size and info.compress_size and info.file_size / info.compress_size > MAX_RATIO:
                raise UnsafeArchiveError("compression ratio")
            total += info.file_size
            if total > MAX_TOTAL_BYTES: raise UnsafeArchiveError("total size")
            out.append((name, zf.read(info), mime_for(ext)))
    if not out: raise UnsafeArchiveError("no supported members")
    return out
```

`_store_attachments(email, owner)` returns a selection result consumed by `_analyze` and later modules:

```python
@dataclass
class AttachmentSelection:
    evidence: list[tuple[UUID, EvidenceRole]]   # (file_id, role) — persisted by module 05
    primary_file_id: UUID | None                # XML member > PDF member > standalone PDF > standalone XML
    primary_preview: str | None                 # for guardrails + classification
```

Flow: for each selected attachment → `files.upload` (module 02's scan gate applies) → if `scan_status` ∈ {THREAT, FAILED}: `repository.mark_blocked(email, [MALWARE_VIOLATION])` with new violation code `attachment.malware` ("El archivo no pasó el análisis antivirus de AWS") and stop. If a `.zip`: upload the zip itself (`role=archive`), then `expand_zip` → upload each member; pick roles: first XML → `primary`, other XMLs `secondary`, PDFs `secondary`; no zip: standalone PDF or XML → `primary`. `UnsafeArchiveError` → blocked with the existing `attachment.unreadable` violation.

Blocking semantics change in `_analyze` (:83–91): replace `parse_status != PARSED → blocked` with:
- no primary at all → blocked (`attachment.unreadable`)
- primary is a PDF with `parse_status != PARSED` (image-only/scanned) → **do not block**; proceed to the run — module 04 decides via Textract or declares `no_info`
- primary is XML with `parse_status != PARSED` (unparseable XML) → proceed as well; the LLM-on-XML fallback in module 04 handles it before `no_info`

Guardrail text (`_guard_text`) uses `primary_preview` when available instead of `attachments[0]` text. `bills.register_source` keeps hashing the **primary** file's bytes for `attachment_sha256` (dedup semantics unchanged: duplicate XML → duplicate bill).

`start_file_run` mirrors this: after the existing upload, if the uploaded file is a zip → expand + upload members + same role selection; pass the `AttachmentSelection` into `start_run` (module 05 persists it as `agent_run_files` rows on the `bill_source`).

Self-check: simulate an email with a ZIP containing `factura.xml` + `factura.pdf` → inbox reaches `analyzing` with 3 evidence rows (archive/primary/secondary) and `primary_file_id` = XML's; ZIP with 1000 entries → blocked `attachment.unreadable`; console `POST /files` of a `.zip` → accepted, run starts on the XML.

## Dependencies

- Module 02 (`FilesService.upload` scan gate, `FileScanStatus`).
- stdlib `zipfile`, `io`, `os`, `mimetypes` — no new packages.

## Integration Notes

- `AttachmentSelection.evidence` is the exact input module 05 persists; keep the tuple shape `(file_id, role)` stable.
- `EvidenceRole` literal lives in `backend/contracts/files.py` (module 02/05 define the enum; this module only uses it).
- Mail cap stays 10 MB per attachment (`MAX_ATTACHMENT_BYTES`), upload cap 25 MB — ZIP expansion limits are separate and stricter.
- Outlook selector must mirror Gmail's exactly (`_outlook_pdf_attachment` → multi-select) so both providers share the selection policy.
