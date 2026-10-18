from dataclasses import dataclass
from datetime import date

from contracts.demo import DemoSectionId, KitDestinations
from contracts.inbox import InboxEmailStatus
from modules.demo.catalog import (
    DEMO_SCENARIOS,
    SECTION_TITLES,
    DemoScenario,
    LaunchContext,
    expected_outcome,
)
from modules.demo.documents import zip_archive

KIT_NONCE_BASE = 7000
KIT_ROOT = "demo-kit"
README_NAME = "README.md"
EXCLUDED_FILE_NAME = "README-in-app-only.txt"
SECTION_FOLDERS: dict[DemoSectionId, str] = {
    section: f"{position:02d}-{section.value.replace('_', '-')}"
    for position, section in enumerate(SECTION_TITLES, start=1)
}
OUTCOME_LABELS: dict[InboxEmailStatus, str] = {
    InboxEmailStatus.PAID: "Paid",
    InboxEmailStatus.REVIEW: "Escalated to a person",
    InboxEmailStatus.HELD: "Held",
    InboxEmailStatus.DUPLICATE: "Duplicate",
    InboxEmailStatus.BLOCKED: "Blocked",
    InboxEmailStatus.NO_INVOICE: "Not an invoice",
    InboxEmailStatus.NO_INFO: "Missing information",
    InboxEmailStatus.ERROR: "Error",
}


@dataclass(frozen=True)
class KitFile:
    path: str
    content: bytes


def kit_nonce(scenario: DemoScenario) -> int:
    return KIT_NONCE_BASE + DEMO_SCENARIOS.index(scenario)


def scenario_kit_files(scenario: DemoScenario, today: date) -> list[KitFile]:
    folder = _scenario_folder(scenario)
    if not scenario.is_kit_exportable:
        explanation = f"{scenario.title}\n\n{scenario.in_app_only_reason}\n"
        return [KitFile(f"{folder}/{EXCLUDED_FILE_NAME}", explanation.encode())]
    context = LaunchContext(today=today, nonce=kit_nonce(scenario))
    files: list[KitFile] = []
    for step_number, step in enumerate(scenario.steps, start=1):
        message = step.build(context)
        files.extend(
            KitFile(f"{folder}/step-{step_number}-{attachment.filename}", attachment.content)
            for attachment in message.attachments
        )
        if scenario.channel == "email":
            suggested_email = f"Subject: {message.subject}\n\n{message.body}\n"
            files.append(
                KitFile(f"{folder}/step-{step_number}-email.txt", suggested_email.encode())
            )
    return files


def build_kit_zip(
    scenarios: list[DemoScenario],
    today: date,
    destinations: KitDestinations,
    is_guardrail_enforced: bool,
) -> bytes:
    members = {
        f"{KIT_ROOT}/{README_NAME}": render_kit_readme(
            scenarios, destinations, is_guardrail_enforced
        ).encode()
    }
    for scenario in scenarios:
        for kit_file in scenario_kit_files(scenario, today):
            members[f"{KIT_ROOT}/{kit_file.path}"] = kit_file.content
    return zip_archive(members)


def render_kit_readme(
    scenarios: list[DemoScenario], destinations: KitDestinations, is_guardrail_enforced: bool
) -> str:
    email = destinations.email_address or "the Gmail inbox connected in the console"
    whatsapp = destinations.whatsapp_number or "the WhatsApp sandbox number shown in the console"
    rows = [
        _readme_row(position, scenario, is_guardrail_enforced)
        for position, scenario in enumerate(scenarios, start=1)
    ]
    in_app_only = [
        f"- `{scenario.scenario_id}`: {scenario.in_app_only_reason}"
        for scenario in scenarios
        if scenario.in_app_only_reason
    ]
    return "\n".join(
        [
            "# Andescape Labs demo kit",
            "",
            "Andescape Labs, Inc. pays a US + LatAm team. Send these files to the demo inbox and "
            "watch the agent decide.",
            "",
            "## Where to send",
            "",
            f"- Email: {email}",
            f"- WhatsApp: {whatsapp}. Register your phone first as the sandbox sender in the "
            "console (Inbox, WhatsApp, sandbox).",
            "",
            "## Before you send",
            "",
            "Add your own email address as a trusted forwarder in the demo panel (Inbox, Demo "
            "scenarios, Send it yourself). The agent then judges the payee from the document "
            "instead of escalating because the sender is unknown.",
            "",
            "Send the steps of a scenario in order and wait for each one to finish. Each "
            "`step-N-email.txt` has a suggested subject and body; attach the `step-N-*` files.",
            "",
            "## Scenarios",
            "",
            "| # | Scenario | Files | Send via | Expected outcome | Key rules |",
            "|---|---|---|---|---|---|",
            *rows,
            "",
            "## In-app only",
            "",
            *in_app_only,
            "",
            "Re-sending the same file is caught as a duplicate on purpose. Ask the presenter to "
            "reset the demo to start over. Due dates are relative to the export day; download a "
            "fresh kit from the app if this one is old.",
            "",
        ]
    )


def _readme_row(position: int, scenario: DemoScenario, is_guardrail_enforced: bool) -> str:
    expectations = [expected_outcome(step, is_guardrail_enforced) for step in scenario.steps]
    outcomes = " → ".join(OUTCOME_LABELS[expectation.outcome] for expectation in expectations)
    rule_ids = sorted({rule_id for expectation in expectations for rule_id in expectation.rule_ids})
    files = "in-app only" if not scenario.is_kit_exportable else f"`{_scenario_folder(scenario)}/`"
    return (
        f"| {position} | {scenario.title} | {files} | {scenario.channel} | {outcomes} | "
        f"{', '.join(rule_ids) or '-'} |"
    )


def _scenario_folder(scenario: DemoScenario) -> str:
    return f"{SECTION_FOLDERS[scenario.section]}/{scenario.scenario_id}"
