from uuid import UUID

from contracts.auth import CurrentUser
from contracts.payment_candidates import PaymentCandidateBase
from contracts.payment_policy import (
    BlacklistEntryCreate,
    BlacklistEntryRecord,
    BlacklistEntryView,
    BlacklistHit,
    IdentifierKind,
    PayeeCreate,
    PayeeIdentifierCreate,
    PayeeIdentifierRecord,
    PayeeIdentifierView,
    PayeeMatch,
    PayeeRecord,
    PayeeUpdate,
    PayeeView,
    PaymentPolicy,
    PaymentPolicyUpdate,
    PaymentPolicyView,
)
from core.logging_config import get_logger
from modules.payment_policy import matching
from modules.payment_policy.errors import (
    BlacklistEntryMissingError,
    IdentifierMissingError,
    PayeeMissingError,
    PayeeVersionConflictError,
    PolicyMissingError,
)
from modules.payment_policy.normalize import (
    normalize_identifier,
    normalize_name,
    strong_identifiers,
)
from modules.payment_policy.repository import NormalizedIdentifier, PaymentPolicyRepository

logger = get_logger(__name__)


class PaymentPolicyService:
    def __init__(self, repository: PaymentPolicyRepository) -> None:
        self._repository = repository

    async def get_policy(self, owner: CurrentUser) -> PaymentPolicy:
        policy = await self._repository.get_active_policy(owner.user_id)
        if policy is None:
            raise PolicyMissingError
        return policy

    async def get_policy_view(self, owner: CurrentUser) -> PaymentPolicyView:
        return _to_policy_view(await self.get_policy(owner))

    async def update_policy(
        self, owner: CurrentUser, changes: PaymentPolicyUpdate
    ) -> PaymentPolicyView:
        policy = await self._repository.activate_policy(owner.user_id, changes, owner.user_id)
        logger.info("payment_policy_activated", owner_id=owner.user_id, version=policy.version)
        return _to_policy_view(policy)

    async def list_payees(self, owner: CurrentUser) -> list[PayeeView]:
        payees = await self._repository.list_payees(owner.user_id)
        identifiers = await self._repository.list_identifiers(
            owner.user_id, [payee.payee_id for payee in payees]
        )
        return [_to_payee_view(payee, identifiers) for payee in payees]

    async def get_payee(self, owner: CurrentUser, payee_id: UUID) -> PayeeView:
        payee = await self._require_payee(owner.user_id, payee_id)
        return await self._payee_view(owner.user_id, payee)

    async def create_payee(self, owner: CurrentUser, payee: PayeeCreate) -> PayeeView:
        identifiers = [_normalized_identifier(identifier) for identifier in payee.identifiers]
        created = await self._repository.create_payee(
            owner.user_id, payee, normalize_name(payee.display_name), identifiers
        )
        logger.info("payee_created", payee_id=created.payee_id, kind=created.kind)
        return await self._payee_view(owner.user_id, created)

    async def update_payee(
        self, owner: CurrentUser, payee_id: UUID, changes: PayeeUpdate
    ) -> PayeeView:
        normalized_name = (
            normalize_name(changes.display_name) if changes.display_name is not None else None
        )
        updated = await self._repository.update_payee(
            owner.user_id, payee_id, changes, normalized_name
        )
        if updated is None:
            await self._require_payee(owner.user_id, payee_id)
            raise PayeeVersionConflictError
        logger.info("payee_updated", payee_id=payee_id, version=updated.version)
        return await self._payee_view(owner.user_id, updated)

    async def delete_payee(self, owner: CurrentUser, payee_id: UUID) -> None:
        was_deleted = await self._repository.delete_payee(owner.user_id, payee_id)
        if not was_deleted:
            raise PayeeMissingError
        logger.info("payee_deleted", payee_id=payee_id)

    async def add_identifier(
        self, owner: CurrentUser, payee_id: UUID, identifier: PayeeIdentifierCreate
    ) -> PayeeView:
        payee = await self._require_payee(owner.user_id, payee_id)
        await self._repository.add_identifier(
            owner.user_id, payee_id, _normalized_identifier(identifier)
        )
        return await self._payee_view(owner.user_id, payee)

    async def delete_identifier(
        self, owner: CurrentUser, payee_id: UUID, identifier_id: UUID
    ) -> None:
        was_deleted = await self._repository.delete_identifier(
            owner.user_id, payee_id, identifier_id
        )
        if not was_deleted:
            raise IdentifierMissingError

    async def list_blacklist(self, owner: CurrentUser) -> list[BlacklistEntryView]:
        entries = await self._repository.list_blacklist(owner.user_id)
        return [_to_blacklist_view(entry) for entry in entries]

    async def add_blacklist_entry(
        self, owner: CurrentUser, entry: BlacklistEntryCreate
    ) -> BlacklistEntryView:
        created = await self._repository.add_blacklist_entry(
            owner.user_id,
            entry.kind,
            normalize_identifier(entry.kind, entry.value),
            entry.reason,
        )
        logger.info("blacklist_entry_added", entry_id=created.entry_id, kind=created.kind)
        return _to_blacklist_view(created)

    async def delete_blacklist_entry(self, owner: CurrentUser, entry_id: UUID) -> None:
        was_deleted = await self._repository.delete_blacklist_entry(owner.user_id, entry_id)
        if not was_deleted:
            raise BlacklistEntryMissingError

    async def match_payee(
        self, owner_id: UUID, candidate: PaymentCandidateBase, sender: str
    ) -> PayeeMatch:
        return await matching.match_payee(self._repository, owner_id, candidate, sender)

    async def find_blacklist_hits(
        self, owner_id: UUID, candidate: PaymentCandidateBase, sender: str
    ) -> list[BlacklistHit]:
        identifiers = strong_identifiers(candidate, sender)
        if candidate.payee_name:
            identifiers.append((IdentifierKind.ALIAS, normalize_name(candidate.payee_name)))
        return await self._repository.find_blacklist_hits(owner_id, identifiers)

    async def _require_payee(self, owner_id: UUID, payee_id: UUID) -> PayeeRecord:
        payee = await self._repository.get_payee(owner_id, payee_id)
        if payee is None:
            raise PayeeMissingError
        return payee

    async def _payee_view(self, owner_id: UUID, payee: PayeeRecord) -> PayeeView:
        identifiers = await self._repository.list_identifiers(owner_id, [payee.payee_id])
        return _to_payee_view(payee, identifiers)


def _normalized_identifier(identifier: PayeeIdentifierCreate) -> NormalizedIdentifier:
    return (
        identifier.kind,
        normalize_identifier(identifier.kind, identifier.value),
        identifier.value.strip(),
    )


def _to_policy_view(policy: PaymentPolicy) -> PaymentPolicyView:
    return PaymentPolicyView(
        policy_id=policy.policy_id,
        version=policy.version,
        created_at=policy.created_at,
        hard_cap_per_payment_usd=policy.hard_cap_per_payment_usd,
        auto_pay_max_usd=policy.auto_pay_max_usd,
        monthly_budget_usd=policy.monthly_budget_usd,
        category_monthly_budgets_usd=policy.category_monthly_budgets_usd,
        allowed_categories=policy.allowed_categories,
        allowed_currencies=policy.allowed_currencies,
        duplicate_window_days=policy.duplicate_window_days,
        min_field_confidence=policy.min_field_confidence,
        min_category_confidence=policy.min_category_confidence,
        checker_review_low=policy.checker_review_low,
        checker_review_high=policy.checker_review_high,
    )


def _to_payee_view(payee: PayeeRecord, identifiers: list[PayeeIdentifierRecord]) -> PayeeView:
    return PayeeView(
        payee_id=payee.payee_id,
        kind=payee.kind,
        display_name=payee.display_name,
        status=payee.status,
        payment_method=payee.payment_method,
        default_category=payee.default_category,
        currency=payee.currency,
        per_payment_max_usd=payee.per_payment_max_usd,
        monthly_budget_usd=payee.monthly_budget_usd,
        agreed_amount_usd=payee.agreed_amount_usd,
        agreed_tolerance_pct=payee.agreed_tolerance_pct,
        attributes=payee.attributes,
        version=payee.version,
        identifiers=[
            PayeeIdentifierView(
                identifier_id=identifier.identifier_id,
                kind=identifier.kind,
                normalized_value=identifier.normalized_value,
                raw_value=identifier.raw_value,
            )
            for identifier in identifiers
            if identifier.payee_id == payee.payee_id
        ],
    )


def _to_blacklist_view(entry: BlacklistEntryRecord) -> BlacklistEntryView:
    return BlacklistEntryView(
        entry_id=entry.entry_id,
        kind=entry.kind,
        normalized_value=entry.normalized_value,
        reason=entry.reason,
        created_at=entry.created_at,
    )
