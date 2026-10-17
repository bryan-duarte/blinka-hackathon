# Risks & Mitigations

## Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| GuardDuty tagging must be enabled **before** the first upload; late enablement = silently untagged objects (poll always times out) | high | Terraform creates the protection plan with tagging ENABLED in the same apply as the bucket; 01 includes a manual upload + tag verification step before any backend work |
| Poll timeout (60s) too tight for large/queued scans → legitimate bills blocked | med | Configurable `scan_timeout_seconds`; scan latency is typically seconds; timeout also surfaced as `scan_status=failed` so the UI shows why it blocked |
| Zip bombs / path traversal in `expand_zip` | high | Hard limits (≤20 entries, ≤50 MB total, compression-ratio check), member allow-list `.pdf/.xml` only, basename sanitization, skip `__MACOSX/` |
| XXE / billion-laughs via crafted e-invoice XML | high | Parse with `defusedxml.ElementTree` only; never stdlib `xml.etree` directly |
| XML from a country outside the registry (Brazil NFS-e municipal variants, Argentina, etc.) | med | `detect_format` returns `UNKNOWN` → LLM fallback on the XML text (country/currency may be missing → rules fail-closed to review); fixtures prove the registry path, registry is trivially extensible per namespace |
| Wrong country inference on UBL (supplier address missing) | low | Secondary hints: DIAN/SUNAT `cbc:CustomizationID`/`cbc:ProfileID` URNs; if both absent, country stays empty and rules treat it as low-confidence |
| Textract cost/limits if a campaign of image PDFs arrives | low | ~$0.01/page, sync API per file only as last resort; natural ceiling from 10 MB attachment / 25 MB upload caps |
| GuardDuty service-role trust shape differs from plan snippet | med | Spec marks the exact service principal as verify-at-apply; console fallback documented |
| S3-only breaks contribution without AWS credentials | med | Documented prerequisite (`panoptico` profile); `malware_scan_enabled=False` escape hatch exists but is not the demo configuration |
| `get_object_tagging` needs extra IAM permission easy to forget | low | Backend policy in Terraform explicitly includes `s3:GetObjectTagging` |
| Removing MinIO leaves stale local objects | low | One-way migration; MinIO data is demo-only, no backfill planned |

## Integration Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| `bill_sources.file_id` consumers (duplicate navigation in `DecisionCard`) break if left stale | med | Column untouched and still populated (first/primary file); new `agent_run_files` becomes additive source of truth |
| Relaxing the unreadable-attachment block lets junk flow to the LLM (cost/prompt-injection) | med | Guardrails still screen subject+body+primary preview before the run; Textract output is mapped deterministically, not re-prompted; XML/ZIP never reach the LLM unless the deterministic parse already failed |
| Frontend blob-download for large PDFs holds memory | low | Caps are 10 MB (mail) / 25 MB (upload); acceptable |
| `InboxEmailStatus.NO_INFO` missing in older clients | low | Additive enum value; frontend ships in the same change |

## Edge Cases Identified

- ZIP contains XML only → XML is primary; PDF absent; roles: archive + primary.
- ZIP contains neither XML nor PDF → treated as unreadable attachment → blocked (`attachment.unreadable`), same as today.
- Both standalone XML and standalone PDF attachments (no ZIP) → XML wins, PDF secondary.
- Password-protected ZIP → `zipfile.BadZipFile`/`RuntimeError` on read → blocked as unreadable (no password guessing).
- Duplicate XML e-invoice → existing `content_sha256`/fingerprint dedup applies unchanged (hash the primary file's bytes).
- Scan says `UNSUPPORTED` (rare for pdf/zip/xml) → file proceeds, evidence badge shows "Sin escaneo".
- All extraction methods fail on a real bill → `extraction_failed` event → `no_info` status (not ERROR) — the "last option before no info" contract.
- Same email retried → existing `(provider, external_message_id)` dedupe; evidence rows are only written once per source.
- Console upload of a bare `.xml` (no ZIP) → primary=xml, deterministic path.
