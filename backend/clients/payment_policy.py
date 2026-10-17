from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.payment_candidates import PaymentCandidateBase
from contracts.payment_policy import (
    BlacklistEntryCreate,
    BlacklistEntryView,
    BlacklistHit,
    PayeeCreate,
    PayeeIdentifierCreate,
    PayeeMatch,
    PayeeUpdate,
    PayeeView,
    PaymentPolicy,
    PaymentPolicyUpdate,
    PaymentPolicyView,
)

if TYPE_CHECKING:
    from modules.payment_policy.service import PaymentPolicyService


class PaymentPolicyClient:
    def __init__(self, service: "PaymentPolicyService") -> None:
        self._service = service

    async def get_policy(self, owner: CurrentUser) -> PaymentPolicy:
        return await self._service.get_policy(owner)

    async def get_policy_view(self, owner: CurrentUser) -> PaymentPolicyView:
        return await self._service.get_policy_view(owner)

    async def update_policy(
        self, owner: CurrentUser, changes: PaymentPolicyUpdate
    ) -> PaymentPolicyView:
        return await self._service.update_policy(owner, changes)

    async def list_payees(self, owner: CurrentUser) -> list[PayeeView]:
        return await self._service.list_payees(owner)

    async def get_payee(self, owner: CurrentUser, payee_id: UUID) -> PayeeView:
        return await self._service.get_payee(owner, payee_id)

    async def create_payee(self, owner: CurrentUser, payee: PayeeCreate) -> PayeeView:
        return await self._service.create_payee(owner, payee)

    async def update_payee(
        self, owner: CurrentUser, payee_id: UUID, changes: PayeeUpdate
    ) -> PayeeView:
        return await self._service.update_payee(owner, payee_id, changes)

    async def delete_payee(self, owner: CurrentUser, payee_id: UUID) -> None:
        await self._service.delete_payee(owner, payee_id)

    async def add_identifier(
        self, owner: CurrentUser, payee_id: UUID, identifier: PayeeIdentifierCreate
    ) -> PayeeView:
        return await self._service.add_identifier(owner, payee_id, identifier)

    async def delete_identifier(
        self, owner: CurrentUser, payee_id: UUID, identifier_id: UUID
    ) -> None:
        await self._service.delete_identifier(owner, payee_id, identifier_id)

    async def list_blacklist(self, owner: CurrentUser) -> list[BlacklistEntryView]:
        return await self._service.list_blacklist(owner)

    async def add_blacklist_entry(
        self, owner: CurrentUser, entry: BlacklistEntryCreate
    ) -> BlacklistEntryView:
        return await self._service.add_blacklist_entry(owner, entry)

    async def delete_blacklist_entry(self, owner: CurrentUser, entry_id: UUID) -> None:
        await self._service.delete_blacklist_entry(owner, entry_id)

    async def match_payee(
        self, owner_id: UUID, candidate: PaymentCandidateBase, sender: str
    ) -> PayeeMatch:
        return await self._service.match_payee(owner_id, candidate, sender)

    async def find_blacklist_hits(
        self, owner_id: UUID, candidate: PaymentCandidateBase, sender: str
    ) -> list[BlacklistHit]:
        return await self._service.find_blacklist_hits(owner_id, candidate, sender)
