import base64
import html
import re
from datetime import datetime
from pathlib import PurePath

from contracts.files import EVIDENCE_MIME_BY_EXTENSION
from contracts.mail_gateway import MAX_EVIDENCE_ATTACHMENTS, FetchedAttachment

HTML_CONTENT_TYPE = "html"
FILE_ATTACHMENT_ODATA_SUFFIX = "fileAttachment"
RESPONSE_DATA_KEY = "response_data"
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


def graph_response(tool_data: dict) -> dict:
    return tool_data.get(RESPONSE_DATA_KEY) or tool_data


def sender(message: dict) -> str:
    sender_email_address = (message.get("from") or {}).get("emailAddress") or {}
    return sender_email_address.get("address") or ""


def body_text(message: dict) -> str:
    message_body = message.get("body") or {}
    content = message_body.get("content") or ""
    is_html = (message_body.get("contentType") or "").lower() == HTML_CONTENT_TYPE
    if not is_html:
        return content
    return html.unescape(HTML_TAG_PATTERN.sub(" ", content)).strip()


def received_at(message: dict) -> datetime | None:
    raw_received_at = message.get("receivedDateTime")
    if not raw_received_at:
        return None
    try:
        return datetime.fromisoformat(raw_received_at)
    except ValueError:
        return None


def evidence_attachments(attachments_data: dict) -> list[FetchedAttachment]:
    selected_attachments = []
    for attachment in graph_response(attachments_data).get("value") or []:
        filename = attachment.get("name") or ""
        evidence_mime = EVIDENCE_MIME_BY_EXTENSION.get(PurePath(filename).suffix.lower())
        is_file_attachment = (attachment.get("@odata.type") or "").endswith(
            FILE_ATTACHMENT_ODATA_SUFFIX
        )
        is_downloadable_evidence = (
            is_file_attachment and evidence_mime is not None and attachment.get("contentBytes")
        )
        if is_downloadable_evidence:
            selected_attachments.append(
                FetchedAttachment(
                    filename=filename,
                    mime=evidence_mime,
                    content=base64.b64decode(attachment["contentBytes"]),
                )
            )
    return selected_attachments[:MAX_EVIDENCE_ATTACHMENTS]
