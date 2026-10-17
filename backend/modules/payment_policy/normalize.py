import re
import unicodedata
from email.utils import parseaddr
from urllib.parse import urlsplit

from contracts.payment_candidates import (
    CompanyCandidate,
    PaymentCandidateBase,
    PersonCandidate,
    ServiceCandidate,
)
from contracts.payment_policy import IdentifierKind
from core.identifiers import canonical_identifier

LEGAL_SUFFIX_WORDS = frozenset(
    {"spa", "sa", "ltda", "llc", "inc", "corp", "sas", "eirl", "gmbh", "s", "a"}
)
NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
WEB_PREFIX = "www."
URL_SCHEME_SEPARATOR = "//"
EMAIL_SEPARATOR = "@"

StrongIdentifier = tuple[IdentifierKind, str]


def normalize_name(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold()
    words = NON_ALPHANUMERIC.sub(" ", folded).split()
    while len(words) > 1 and words[-1] in LEGAL_SUFFIX_WORDS:
        words.pop()
    return " ".join(words)


def normalize_identifier(kind: IdentifierKind, raw_value: str) -> str:
    if kind is IdentifierKind.EMAIL:
        return normalize_email(raw_value)
    if kind is IdentifierKind.DOMAIN:
        return normalize_domain(raw_value)
    if kind is IdentifierKind.ALIAS:
        return normalize_name(raw_value)
    return canonical_identifier(raw_value)


def normalize_email(raw_value: str) -> str:
    _, address = parseaddr(raw_value)
    return (address or raw_value).strip().casefold()


def normalize_domain(raw_value: str) -> str:
    candidate = raw_value.strip().casefold()
    if EMAIL_SEPARATOR in candidate:
        candidate = normalize_email(candidate).rpartition(EMAIL_SEPARATOR)[2]
    if URL_SCHEME_SEPARATOR in candidate:
        candidate = urlsplit(candidate).hostname or ""
    candidate = candidate.split("/", 1)[0]
    return candidate.removeprefix(WEB_PREFIX)


def sender_identifiers(sender: str) -> list[StrongIdentifier]:
    sender_email = normalize_email(sender) if sender else ""
    if EMAIL_SEPARATOR not in sender_email:
        return []
    return [
        (IdentifierKind.EMAIL, sender_email),
        (IdentifierKind.DOMAIN, normalize_domain(sender_email)),
    ]


def strong_identifiers(candidate: PaymentCandidateBase, sender: str) -> list[StrongIdentifier]:
    identifiers = [*bill_identifiers(candidate), *sender_identifiers(sender)]
    return list(dict.fromkeys(identifiers))


def bill_identifiers(candidate: PaymentCandidateBase) -> list[StrongIdentifier]:
    raw_identifiers: list[tuple[IdentifierKind, str | None]] = [
        (IdentifierKind.BANK_ACCOUNT, candidate.bank_account),
        (IdentifierKind.EMAIL, candidate.payee_email),
        *_kind_identifiers(candidate),
    ]
    normalized = [
        (kind, normalize_identifier(kind, raw_value))
        for kind, raw_value in raw_identifiers
        if raw_value and raw_value.strip()
    ]
    return list(dict.fromkeys(identifier for identifier in normalized if identifier[1]))


def identifier_key(kind: IdentifierKind, normalized_value: str) -> str:
    return f"{kind}:{normalized_value}"


def _kind_identifiers(candidate: PaymentCandidateBase) -> list[tuple[IdentifierKind, str | None]]:
    if isinstance(candidate, ServiceCandidate):
        return [
            (IdentifierKind.SERVICE_ACCOUNT_ID, candidate.service_account_id),
            (IdentifierKind.DOMAIN, candidate.provider_domain),
        ]
    if isinstance(candidate, PersonCandidate):
        return [(IdentifierKind.TAX_ID, candidate.national_id)]
    if isinstance(candidate, CompanyCandidate):
        return [(IdentifierKind.TAX_ID, candidate.tax_id)]
    return []
