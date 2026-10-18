import random
from typing import Literal

ToolPhase = Literal["start", "finish"]

TOOL_PHRASES: dict[str, dict[ToolPhase, tuple[str, ...]]] = {
    "classify_document": {
        "start": (
            "Reading the document to see whether it is an invoice…",
            "Classifying the document: bill, quote or credit note?",
            "Checking what kind of document arrived…",
            "Looking at the document to see if there is anything to pay…",
        ),
        "finish": (
            "Done, I know what kind of document this is.",
            "Document classified.",
            "Document type identified.",
        ),
    },
    "extract_invoice": {
        "start": (
            "Pulling amount, currency and payee from the document…",
            "Extracting the key invoice details…",
            "Reading the invoice number and due date…",
            "Noting who to pay, how much and by when…",
        ),
        "finish": (
            "Invoice details extracted.",
            "I have the amount, currency and payee.",
            "Done, the key details are noted.",
        ),
    },
    "register_bill": {
        "start": (
            "Looking up the payee in the allow list…",
            "Checking whether this invoice arrived before…",
            "Registering the bill and comparing it with earlier ones…",
        ),
        "finish": (
            "Bill registered.",
            "Payee checked and bill registered.",
            "Done, I know whether this invoice is new.",
        ),
    },
    "evaluate_rules": {
        "start": (
            "Comparing against the company's payment rules…",
            "Checking limits, budget and payees…",
            "Running the invoice through the payment rules…",
            "Verifying caps and the budget for the period…",
        ),
        "finish": (
            "Payment rules checked.",
            "Done, every rule is checked.",
            "Finished comparing against the company's rules.",
        ),
    },
    "run_checker": {
        "start": (
            "Running a second review before paying…",
            "Verifying everything matches the agreement…",
            "Asking for a second opinion before moving money…",
        ),
        "finish": (
            "Second review finished.",
            "The checker gave its opinion.",
            "Done, the second review is complete.",
        ),
    },
    "settle_decision": {
        "start": (
            "Recording the decision and its explanation…",
            "Writing down why it was decided this way…",
            "Saving the decision to the ledger…",
        ),
        "finish": (
            "Decision recorded.",
            "Done, the decision is saved with its explanation.",
            "Decision made and logged.",
        ),
    },
}
TOOL_ERROR_PHRASES: tuple[str, ...] = (
    "This step could not be completed.",
    "Something failed in this step.",
    "This step did not go as expected.",
)
STEP_PHRASES: dict[str, tuple[str, ...]] = {
    "started": (
        "The agent started working on this invoice.",
        "The agent picked up the document and started reviewing it.",
    ),
    "classified": ("Document classified.",),
    "not_a_bill": (
        "This does not look like a bill to pay.",
        "I found nothing to pay in this document.",
    ),
    "extracted": ("Invoice details extracted.",),
    "extraction_failed": (
        "The invoice details could not be read.",
        "The document does not have enough details to pay.",
    ),
    "claimed": ("Bill registered.",),
    "decided": ("Decision made.",),
    "decision_failed": (
        "Something failed while deciding; the bill stays in review.",
        "I could not finish the checks; a person must review it.",
    ),
    "completed": ("The agent finished.", "Review finished."),
    "cancelled": ("The review was interrupted.",),
    "failed": ("The review failed.", "The agent could not finish the review."),
}


def pick_tool_phrase(tool: str, phase: ToolPhase) -> str:
    return random.choice(TOOL_PHRASES[tool][phase])


def pick_tool_error_phrase() -> str:
    return random.choice(TOOL_ERROR_PHRASES)


def pick_step_phrase(step: str) -> str | None:
    step_phrases = STEP_PHRASES.get(step)
    if step_phrases is None:
        return None
    return random.choice(step_phrases)
