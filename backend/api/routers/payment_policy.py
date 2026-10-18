from uuid import UUID

from fastapi import APIRouter, status

from api.deps import ClientsDep, CurrentUserDep
from contracts.payment_policy import (
    BlacklistEntryCreate,
    BlacklistEntryView,
    PayeeCreate,
    PayeeIdentifierCreate,
    PayeeUpdate,
    PayeeView,
    PaymentPolicyUpdate,
    PaymentPolicyView,
    TrustedForwarderCreate,
    TrustedForwarderView,
)

payment_policy_router = APIRouter(tags=["payment-policy"])


@payment_policy_router.get("/payment-policy", response_model=PaymentPolicyView)
async def get_policy(user: CurrentUserDep, clients: ClientsDep) -> PaymentPolicyView:
    return await clients.payment_policy.get_policy_view(user)


@payment_policy_router.put("/payment-policy", response_model=PaymentPolicyView)
async def update_policy(
    changes: PaymentPolicyUpdate, user: CurrentUserDep, clients: ClientsDep
) -> PaymentPolicyView:
    return await clients.payment_policy.update_policy(user, changes)


@payment_policy_router.get("/payees", response_model=list[PayeeView])
async def list_payees(user: CurrentUserDep, clients: ClientsDep) -> list[PayeeView]:
    return await clients.payment_policy.list_payees(user)


@payment_policy_router.post(
    "/payees", response_model=PayeeView, status_code=status.HTTP_201_CREATED
)
async def create_payee(payee: PayeeCreate, user: CurrentUserDep, clients: ClientsDep) -> PayeeView:
    return await clients.payment_policy.create_payee(user, payee)


@payment_policy_router.get("/payees/{payee_id}", response_model=PayeeView)
async def get_payee(payee_id: UUID, user: CurrentUserDep, clients: ClientsDep) -> PayeeView:
    return await clients.payment_policy.get_payee(user, payee_id)


@payment_policy_router.patch("/payees/{payee_id}", response_model=PayeeView)
async def update_payee(
    payee_id: UUID, changes: PayeeUpdate, user: CurrentUserDep, clients: ClientsDep
) -> PayeeView:
    return await clients.payment_policy.update_payee(user, payee_id, changes)


@payment_policy_router.delete("/payees/{payee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payee(payee_id: UUID, user: CurrentUserDep, clients: ClientsDep) -> None:
    await clients.payment_policy.delete_payee(user, payee_id)


@payment_policy_router.post("/payees/{payee_id}/identifiers", response_model=PayeeView)
async def add_identifier(
    payee_id: UUID, identifier: PayeeIdentifierCreate, user: CurrentUserDep, clients: ClientsDep
) -> PayeeView:
    return await clients.payment_policy.add_identifier(user, payee_id, identifier)


@payment_policy_router.delete(
    "/payees/{payee_id}/identifiers/{identifier_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_identifier(
    payee_id: UUID, identifier_id: UUID, user: CurrentUserDep, clients: ClientsDep
) -> None:
    await clients.payment_policy.delete_identifier(user, payee_id, identifier_id)


@payment_policy_router.get("/blacklist", response_model=list[BlacklistEntryView])
async def list_blacklist(user: CurrentUserDep, clients: ClientsDep) -> list[BlacklistEntryView]:
    return await clients.payment_policy.list_blacklist(user)


@payment_policy_router.post(
    "/blacklist", response_model=BlacklistEntryView, status_code=status.HTTP_201_CREATED
)
async def add_blacklist_entry(
    entry: BlacklistEntryCreate, user: CurrentUserDep, clients: ClientsDep
) -> BlacklistEntryView:
    return await clients.payment_policy.add_blacklist_entry(user, entry)


@payment_policy_router.delete("/blacklist/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blacklist_entry(entry_id: UUID, user: CurrentUserDep, clients: ClientsDep) -> None:
    await clients.payment_policy.delete_blacklist_entry(user, entry_id)


@payment_policy_router.get("/trusted-forwarders", response_model=list[TrustedForwarderView])
async def list_trusted_forwarders(
    user: CurrentUserDep, clients: ClientsDep
) -> list[TrustedForwarderView]:
    return await clients.payment_policy.list_trusted_forwarders(user)


@payment_policy_router.post(
    "/trusted-forwarders",
    response_model=TrustedForwarderView,
    status_code=status.HTTP_201_CREATED,
)
async def add_trusted_forwarder(
    forwarder: TrustedForwarderCreate, user: CurrentUserDep, clients: ClientsDep
) -> TrustedForwarderView:
    return await clients.payment_policy.add_trusted_forwarder(user, forwarder)


@payment_policy_router.delete(
    "/trusted-forwarders/{forwarder_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_trusted_forwarder(
    forwarder_id: UUID, user: CurrentUserDep, clients: ClientsDep
) -> None:
    await clients.payment_policy.delete_trusted_forwarder(user, forwarder_id)
