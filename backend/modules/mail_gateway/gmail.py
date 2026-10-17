from datetime import UTC, datetime

PDF_MIME = "application/pdf"
PDF_EXTENSION = ".pdf"
S3_URL_KEY = "s3url"
MILLISECONDS_PER_SECOND = 1000
ATTACHMENT_ID_KEYS = ("attachmentId", "attachment_id")
FILENAME_KEYS = ("filename", "name")
MIME_KEYS = ("mimeType", "mimetype")


def message_id(trigger_data: dict) -> str:
    return str(trigger_data.get("message_id") or trigger_data.get("id") or "")


def parse_timestamp(raw_timestamp: object) -> datetime | None:
    if raw_timestamp is None:
        return None
    timestamp_text = str(raw_timestamp)
    if timestamp_text.isdigit():
        return datetime.fromtimestamp(int(timestamp_text) / MILLISECONDS_PER_SECOND, tz=UTC)
    try:
        return datetime.fromisoformat(timestamp_text)
    except ValueError:
        return None


def first_pdf_attachment(attachment_list: list[dict]) -> tuple[str, str] | None:
    for attachment in attachment_list:
        attachment_id = _first_present(attachment, ATTACHMENT_ID_KEYS)
        filename = _first_present(attachment, FILENAME_KEYS)
        mime = _first_present(attachment, MIME_KEYS)
        is_pdf = mime == PDF_MIME or filename.lower().endswith(PDF_EXTENSION)
        if attachment_id and is_pdf:
            return attachment_id, filename
    return None


def find_s3url(tool_output: object) -> str | None:
    if isinstance(tool_output, dict):
        if isinstance(tool_output.get(S3_URL_KEY), str):
            return tool_output[S3_URL_KEY]
        nested_values = tool_output.values()
    elif isinstance(tool_output, list):
        nested_values = tool_output
    else:
        return None
    for nested_value in nested_values:
        s3url = find_s3url(nested_value)
        if s3url is not None:
            return s3url
    return None


def _first_present(attachment: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        if attachment.get(key):
            return str(attachment[key])
    return ""
