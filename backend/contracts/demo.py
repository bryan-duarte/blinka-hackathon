from datetime import datetime
from enum import StrEnum
from uuid import UUID

from contracts._base import ApiModel
from contracts.inbox import InboxChannel, InboxEmailStatus


class DemoSectionId(StrEnum):
    HAPPY_PATH = "happy_path"
    FORMATS = "formats"
    DUPLICATES = "duplicates"
    RULES = "rules"
    LIMITS = "limits"
    SECURITY = "security"


class DemoExpectation(ApiModel):
    outcome: InboxEmailStatus
    rule_ids: list[str] = []
    summary: str


class DemoScenarioView(ApiModel):
    scenario_id: str
    section: DemoSectionId
    title: str
    description: str
    channel: InboxChannel
    steps: list[DemoExpectation]
    is_self_sendable: bool
    self_send_hint: str


class DemoSectionView(ApiModel):
    section: DemoSectionId
    title: str
    scenarios: list[DemoScenarioView]


class KitDestinations(ApiModel):
    email_address: str | None
    whatsapp_number: str | None


class DemoCatalogView(ApiModel):
    company_name: str
    sections: list[DemoSectionView]
    is_guardrail_enforced: bool
    is_malware_scan_enabled: bool
    destinations: KitDestinations


class DemoLaunchStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DemoLaunchStepView(ApiModel):
    index: int
    email_id: UUID | None
    status: InboxEmailStatus | None
    expected: DemoExpectation
    is_as_expected: bool | None


class DemoLaunchView(ApiModel):
    launch_id: UUID
    scenario_id: str
    status: DemoLaunchStatus
    steps: list[DemoLaunchStepView]
    started_at: datetime
    error: str | None = None


class DemoResetResult(ApiModel):
    deleted_rows: dict[str, int]
    deleted_objects: int
    seeded_bills: int
    reset_at: datetime
