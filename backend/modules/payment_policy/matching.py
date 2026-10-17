from uuid import UUID

from contracts.payment_candidates import PaymentCandidateBase
from contracts.payment_policy import IdentifierKind, PayeeMatch, PayeeRecord
from modules.payment_policy.normalize import (
    StrongIdentifier,
    bill_identifiers,
    identifier_key,
    normalize_identifier,
    normalize_name,
    sender_identifiers,
)
from modules.payment_policy.repository import PaymentPolicyRepository

SENDER_IDENTIFIER_KINDS = frozenset({IdentifierKind.EMAIL, IdentifierKind.DOMAIN})


async def match_payee(
    repository: PaymentPolicyRepository,
    owner_id: UUID,
    candidate: PaymentCandidateBase,
    sender: str,
) -> PayeeMatch:
    on_bill = bill_identifiers(candidate)
    from_sender = sender_identifiers(sender)
    all_identifiers = list(dict.fromkeys([*on_bill, *from_sender]))
    owners = await repository.find_identifier_owners(owner_id, all_identifiers)
    normalized_payee_name = normalize_name(candidate.payee_name or "")
    name_candidates = await repository.find_payees_by_name(owner_id, normalized_payee_name)
    payee, matched_by = await _resolve_payee(repository, owner_id, owners, name_candidates)
    registered = await _registered_identifiers(repository, owner_id, payee)
    bill_bank_account = (
        normalize_identifier(IdentifierKind.BANK_ACCOUNT, candidate.bank_account)
        if candidate.bank_account
        else None
    )
    return PayeeMatch(
        payee=payee,
        matched_by=matched_by,
        identifier_owners={
            identifier_key(kind, value): payee_id for (kind, value), payee_id in owners.items()
        },
        unknown_identifiers=[
            identifier_key(kind, value) for kind, value in on_bill if (kind, value) not in owners
        ],
        name_candidates=name_candidates,
        registered_bank_accounts=[
            value for kind, value in registered if kind is IdentifierKind.BANK_ACCOUNT
        ],
        registered_senders=[value for kind, value in registered if kind in SENDER_IDENTIFIER_KINDS],
        normalized_payee_name=normalized_payee_name or None,
        bill_bank_account=bill_bank_account or None,
        sender_email=_sender_value(from_sender, IdentifierKind.EMAIL),
        sender_domain=_sender_value(from_sender, IdentifierKind.DOMAIN),
    )


async def _resolve_payee(
    repository: PaymentPolicyRepository,
    owner_id: UUID,
    owners: dict[StrongIdentifier, UUID],
    name_candidates: list[PayeeRecord],
) -> tuple[PayeeRecord | None, IdentifierKind | None]:
    owning_payee_ids = list(dict.fromkeys(owners.values()))
    has_single_identifier_owner = len(owning_payee_ids) == 1
    if has_single_identifier_owner:
        matched_id = owning_payee_ids[0]
        matched_by = next(kind for (kind, _), payee_id in owners.items() if payee_id == matched_id)
        return await repository.get_payee(owner_id, matched_id), matched_by
    is_name_only_match = not owners and len(name_candidates) == 1
    if is_name_only_match:
        return name_candidates[0], IdentifierKind.ALIAS
    return None, None


async def _registered_identifiers(
    repository: PaymentPolicyRepository, owner_id: UUID, payee: PayeeRecord | None
) -> list[StrongIdentifier]:
    if payee is None:
        return []
    identifiers = await repository.list_identifiers(owner_id, [payee.payee_id])
    return [(identifier.kind, identifier.normalized_value) for identifier in identifiers]


def _sender_value(identifiers: list[StrongIdentifier], kind: IdentifierKind) -> str | None:
    return next((value for identifier_kind, value in identifiers if identifier_kind is kind), None)
