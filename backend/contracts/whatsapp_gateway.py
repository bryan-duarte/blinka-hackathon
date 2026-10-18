from datetime import datetime
from enum import StrEnum
from uuid import UUID

from contracts._base import ApiModel, StrictModel
from contracts.mail_gateway import MailAccountStatus


class WhatsAppConnectionMode(StrEnum):
    SANDBOX = "sandbox"
    OWN_NUMBER = "own_number"


class WhatsAppDocumentEvent(StrictModel):
    phone_number_id: str
    message_id: str
    sender_phone: str
    contact_name: str | None
    filename: str
    mime: str
    caption: str = ""
    media_url: str | None
    media_id: str | None
    received_at: datetime | None


class KapsoSetupLink(StrictModel):
    setup_link_id: str
    url: str


class KapsoPhoneNumber(StrictModel):
    phone_number_id: str
    customer_id: str | None
    display_phone_number: str | None
    is_coexistence: bool
    is_sandbox: bool


class RegisterSandboxRequest(ApiModel):
    phone_number: str


class WhatsAppSandboxView(ApiModel):
    connection_id: UUID
    phone_number: str
    sandbox_number: str
    status: MailAccountStatus


class ConfirmWhatsAppRequest(ApiModel):
    setup_link_id: str
    phone_number_id: str
