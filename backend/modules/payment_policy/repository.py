from decimal import Decimal
from uuid import UUID

from sqlalchemy import Delete, Select, delete, func, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.payment_policy import (
    BlacklistEntryRecord,
    BlacklistHit,
    IdentifierKind,
    PayeeCreate,
    PayeeIdentifierRecord,
    PayeeKind,
    PayeeRecord,
    PayeeStatus,
    PayeeUpdate,
    PaymentCategory,
    PaymentMethod,
    PaymentPolicy,
    PaymentPolicyUpdate,
)
from modules.payment_policy.errors import (
    IdentifierTakenError,
    PayeeInUseError,
    PayeeNameTakenError,
)
from modules.payment_policy.models import (
    BLACKLIST_CONSTRAINT,
    PAYEE_IDENTIFIER_CONSTRAINT,
    PAYEE_NAME_CONSTRAINT,
    BlacklistEntryRow,
    PayeeIdentifierRow,
    PayeeRow,
    PaymentPolicyRow,
)
from modules.payment_policy.normalize import StrongIdentifier

FIRST_POLICY_VERSION = 1
POLICY_EDIT_LOCK_CLASS = 7301
PAYEE_VERSION_FIELD = "version"
NULLABLE_PAYEE_COLUMNS = frozenset(
    {
        "default_category",
        "per_payment_max_usd",
        "monthly_budget_usd",
        "agreed_amount_usd",
        "agreed_tolerance_pct",
    }
)

NormalizedIdentifier = tuple[IdentifierKind, str, str]


class PaymentPolicyRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def get_active_policy(self, owner_id: UUID) -> PaymentPolicy | None:
        statement = select(PaymentPolicyRow).where(
            PaymentPolicyRow.owner_id == owner_id, PaymentPolicyRow.is_active
        )
        async with self._sessionmaker() as session:
            policy = (await session.execute(statement)).scalar_one_or_none()
        if policy is None:
            return None
        return _to_policy(policy)

    async def activate_policy(
        self, owner_id: UUID, changes: PaymentPolicyUpdate, created_by: UUID
    ) -> PaymentPolicy:
        serialize_owner_policy_edits = select(
            func.pg_advisory_xact_lock(POLICY_EDIT_LOCK_CLASS, func.hashtext(str(owner_id)))
        )
        active_policy = select(PaymentPolicyRow.id).where(
            PaymentPolicyRow.owner_id == owner_id, PaymentPolicyRow.is_active
        )
        latest_version = select(func.max(PaymentPolicyRow.version)).where(
            PaymentPolicyRow.owner_id == owner_id
        )
        async with self._sessionmaker() as session, session.begin():
            await session.execute(serialize_owner_policy_edits)
            active_policy_id = (await session.execute(active_policy)).scalar_one_or_none()
            current_version = (await session.execute(latest_version)).scalar_one_or_none()
            if active_policy_id is not None:
                await session.execute(
                    update(PaymentPolicyRow)
                    .where(PaymentPolicyRow.id == active_policy_id)
                    .values(is_active=False)
                )
            policy = _policy_row(owner_id, changes, created_by, current_version)
            session.add(policy)
            await session.flush()
            await session.refresh(policy)
        return _to_policy(policy)

    async def list_payees(self, owner_id: UUID) -> list[PayeeRecord]:
        statement = (
            select(PayeeRow).where(PayeeRow.owner_id == owner_id).order_by(PayeeRow.display_name)
        )
        return await self._payees(statement)

    async def get_payee(self, owner_id: UUID, payee_id: UUID) -> PayeeRecord | None:
        statement = select(PayeeRow).where(PayeeRow.id == payee_id, PayeeRow.owner_id == owner_id)
        payees = await self._payees(statement)
        return payees[0] if payees else None

    async def create_payee(
        self,
        owner_id: UUID,
        payee: PayeeCreate,
        normalized_name: str,
        identifiers: list[NormalizedIdentifier],
    ) -> PayeeRecord:
        payee_row = PayeeRow(
            owner_id=owner_id,
            kind=payee.kind,
            display_name=payee.display_name,
            normalized_name=normalized_name,
            status=payee.status,
            payment_method=payee.payment_method,
            default_category=payee.default_category,
            currency=payee.currency.upper(),
            per_payment_max_usd=payee.per_payment_max_usd,
            monthly_budget_usd=payee.monthly_budget_usd,
            agreed_amount_usd=payee.agreed_amount_usd,
            agreed_tolerance_pct=payee.agreed_tolerance_pct,
            attributes=payee.attributes,
        )
        try:
            async with self._sessionmaker() as session, session.begin():
                session.add(payee_row)
                await session.flush()
                session.add_all(
                    [
                        _identifier_row(owner_id, payee_row.id, identifier)
                        for identifier in identifiers
                    ]
                )
        except IntegrityError as integrity_error:
            raise _payee_conflict(integrity_error) from integrity_error
        return _to_payee(payee_row)

    async def update_payee(
        self,
        owner_id: UUID,
        payee_id: UUID,
        changes: PayeeUpdate,
        normalized_name: str | None,
    ) -> PayeeRecord | None:
        changed_columns = {
            column: value
            for column, value in changes.model_dump(
                exclude_unset=True, exclude={PAYEE_VERSION_FIELD}
            ).items()
            if value is not None or column in NULLABLE_PAYEE_COLUMNS
        }
        if "currency" in changed_columns:
            changed_columns["currency"] = changed_columns["currency"].upper()
        if "display_name" in changed_columns:
            changed_columns["normalized_name"] = normalized_name
        statement = (
            update(PayeeRow)
            .where(
                PayeeRow.id == payee_id,
                PayeeRow.owner_id == owner_id,
                PayeeRow.version == changes.version,
            )
            .values(**changed_columns, version=PayeeRow.version + 1, updated_at=func.now())
            .returning(PayeeRow)
        )
        try:
            async with self._sessionmaker() as session:
                payee = (await session.execute(statement)).scalar_one_or_none()
                await session.commit()
        except IntegrityError as integrity_error:
            raise _payee_conflict(integrity_error) from integrity_error
        if payee is None:
            return None
        return _to_payee(payee)

    async def delete_payee(self, owner_id: UUID, payee_id: UUID) -> bool:
        statement = (
            delete(PayeeRow)
            .where(PayeeRow.id == payee_id, PayeeRow.owner_id == owner_id)
            .returning(PayeeRow.id)
        )
        try:
            return await self._deleted(statement)
        except IntegrityError as integrity_error:
            raise PayeeInUseError from integrity_error

    async def add_identifier(
        self, owner_id: UUID, payee_id: UUID, identifier: NormalizedIdentifier
    ) -> PayeeIdentifierRecord:
        identifier_row = _identifier_row(owner_id, payee_id, identifier)
        try:
            async with self._sessionmaker() as session, session.begin():
                session.add(identifier_row)
        except IntegrityError as integrity_error:
            raise IdentifierTakenError from integrity_error
        return _to_identifier(identifier_row)

    async def delete_identifier(self, owner_id: UUID, payee_id: UUID, identifier_id: UUID) -> bool:
        statement = (
            delete(PayeeIdentifierRow)
            .where(
                PayeeIdentifierRow.id == identifier_id,
                PayeeIdentifierRow.payee_id == payee_id,
                PayeeIdentifierRow.owner_id == owner_id,
            )
            .returning(PayeeIdentifierRow.id)
        )
        return await self._deleted(statement)

    async def list_identifiers(
        self, owner_id: UUID, payee_ids: list[UUID]
    ) -> list[PayeeIdentifierRecord]:
        if not payee_ids:
            return []
        statement = (
            select(PayeeIdentifierRow)
            .where(
                PayeeIdentifierRow.owner_id == owner_id,
                PayeeIdentifierRow.payee_id.in_(payee_ids),
            )
            .order_by(PayeeIdentifierRow.kind, PayeeIdentifierRow.normalized_value)
        )
        async with self._sessionmaker() as session:
            identifiers = (await session.execute(statement)).scalars().all()
        return [_to_identifier(identifier) for identifier in identifiers]

    async def find_identifier_owners(
        self, owner_id: UUID, identifiers: list[StrongIdentifier]
    ) -> dict[StrongIdentifier, UUID]:
        if not identifiers:
            return {}
        statement = select(
            PayeeIdentifierRow.kind,
            PayeeIdentifierRow.normalized_value,
            PayeeIdentifierRow.payee_id,
        ).where(
            PayeeIdentifierRow.owner_id == owner_id,
            tuple_(PayeeIdentifierRow.kind, PayeeIdentifierRow.normalized_value).in_(identifiers),
        )
        async with self._sessionmaker() as session:
            owned_identifiers = (await session.execute(statement)).all()
        return {
            (IdentifierKind(kind), normalized_value): payee_id
            for kind, normalized_value, payee_id in owned_identifiers
        }

    async def find_payees_by_name(self, owner_id: UUID, normalized_name: str) -> list[PayeeRecord]:
        if not normalized_name:
            return []
        alias_owners = select(PayeeIdentifierRow.payee_id).where(
            PayeeIdentifierRow.owner_id == owner_id,
            PayeeIdentifierRow.kind == IdentifierKind.ALIAS,
            PayeeIdentifierRow.normalized_value == normalized_name,
        )
        statement = select(PayeeRow).where(
            PayeeRow.owner_id == owner_id,
            or_(PayeeRow.normalized_name == normalized_name, PayeeRow.id.in_(alias_owners)),
        )
        return await self._payees(statement)

    async def find_blacklist_hits(
        self, owner_id: UUID, identifiers: list[StrongIdentifier]
    ) -> list[BlacklistHit]:
        if not identifiers:
            return []
        statement = select(BlacklistEntryRow).where(
            BlacklistEntryRow.owner_id == owner_id,
            tuple_(BlacklistEntryRow.kind, BlacklistEntryRow.normalized_value).in_(identifiers),
        )
        async with self._sessionmaker() as session:
            entries = (await session.execute(statement)).scalars().all()
        return [
            BlacklistHit(
                kind=IdentifierKind(entry.kind),
                normalized_value=entry.normalized_value,
                reason=entry.reason,
            )
            for entry in entries
        ]

    async def list_blacklist(self, owner_id: UUID) -> list[BlacklistEntryRecord]:
        statement = (
            select(BlacklistEntryRow)
            .where(BlacklistEntryRow.owner_id == owner_id)
            .order_by(BlacklistEntryRow.created_at.desc())
        )
        async with self._sessionmaker() as session:
            entries = (await session.execute(statement)).scalars().all()
        return [_to_blacklist_entry(entry) for entry in entries]

    async def add_blacklist_entry(
        self, owner_id: UUID, kind: IdentifierKind, normalized_value: str, reason: str
    ) -> BlacklistEntryRecord:
        statement = (
            insert(BlacklistEntryRow)
            .values(owner_id=owner_id, kind=kind, normalized_value=normalized_value, reason=reason)
            .on_conflict_do_nothing(constraint=BLACKLIST_CONSTRAINT)
            .returning(BlacklistEntryRow)
        )
        existing_statement = select(BlacklistEntryRow).where(
            BlacklistEntryRow.owner_id == owner_id,
            BlacklistEntryRow.kind == kind,
            BlacklistEntryRow.normalized_value == normalized_value,
        )
        async with self._sessionmaker() as session, session.begin():
            entry = (await session.execute(statement)).scalar_one_or_none()
            if entry is None:
                entry = (await session.execute(existing_statement)).scalar_one()
        return _to_blacklist_entry(entry)

    async def delete_blacklist_entry(self, owner_id: UUID, entry_id: UUID) -> bool:
        statement = (
            delete(BlacklistEntryRow)
            .where(BlacklistEntryRow.id == entry_id, BlacklistEntryRow.owner_id == owner_id)
            .returning(BlacklistEntryRow.id)
        )
        return await self._deleted(statement)

    async def _payees(self, statement: Select) -> list[PayeeRecord]:
        async with self._sessionmaker() as session:
            payees = (await session.execute(statement)).scalars().all()
        return [_to_payee(payee) for payee in payees]

    async def _deleted(self, statement: Delete) -> bool:
        async with self._sessionmaker() as session:
            deleted_id = (await session.execute(statement)).scalar_one_or_none()
            await session.commit()
        return deleted_id is not None


def _policy_row(
    owner_id: UUID, changes: PaymentPolicyUpdate, created_by: UUID, current_version: int | None
) -> PaymentPolicyRow:
    next_version = FIRST_POLICY_VERSION if current_version is None else current_version + 1
    return PaymentPolicyRow(
        owner_id=owner_id,
        version=next_version,
        is_active=True,
        hard_cap_per_payment_usd=changes.hard_cap_per_payment_usd,
        auto_pay_max_usd=changes.auto_pay_max_usd,
        monthly_budget_usd=changes.monthly_budget_usd,
        category_monthly_budgets_usd={
            str(category): str(budget)
            for category, budget in changes.category_monthly_budgets_usd.items()
        },
        allowed_categories=[str(category) for category in changes.allowed_categories],
        allowed_currencies=[currency.upper() for currency in changes.allowed_currencies],
        duplicate_window_days=changes.duplicate_window_days,
        min_field_confidence=changes.min_field_confidence,
        min_category_confidence=changes.min_category_confidence,
        checker_review_low=changes.checker_review_low,
        checker_review_high=changes.checker_review_high,
        created_by=created_by,
    )


def _identifier_row(
    owner_id: UUID, payee_id: UUID, identifier: NormalizedIdentifier
) -> PayeeIdentifierRow:
    kind, normalized_value, raw_value = identifier
    return PayeeIdentifierRow(
        owner_id=owner_id,
        payee_id=payee_id,
        kind=kind,
        normalized_value=normalized_value,
        raw_value=raw_value,
    )


def _payee_conflict(integrity_error: IntegrityError) -> Exception:
    diagnostics = getattr(integrity_error.orig, "diag", None)
    constraint_name = getattr(diagnostics, "constraint_name", None)
    if constraint_name == PAYEE_NAME_CONSTRAINT:
        return PayeeNameTakenError()
    if constraint_name == PAYEE_IDENTIFIER_CONSTRAINT:
        return IdentifierTakenError()
    return integrity_error


def _to_policy(policy: PaymentPolicyRow) -> PaymentPolicy:
    return PaymentPolicy(
        policy_id=policy.id,
        owner_id=policy.owner_id,
        version=policy.version,
        hard_cap_per_payment_usd=policy.hard_cap_per_payment_usd,
        auto_pay_max_usd=policy.auto_pay_max_usd,
        monthly_budget_usd=policy.monthly_budget_usd,
        category_monthly_budgets_usd={
            PaymentCategory(category): Decimal(budget)
            for category, budget in policy.category_monthly_budgets_usd.items()
        },
        allowed_categories=[PaymentCategory(category) for category in policy.allowed_categories],
        allowed_currencies=list(policy.allowed_currencies),
        duplicate_window_days=policy.duplicate_window_days,
        min_field_confidence=policy.min_field_confidence,
        min_category_confidence=policy.min_category_confidence,
        checker_review_low=policy.checker_review_low,
        checker_review_high=policy.checker_review_high,
        created_at=policy.created_at,
    )


def _to_payee(payee: PayeeRow) -> PayeeRecord:
    return PayeeRecord(
        payee_id=payee.id,
        owner_id=payee.owner_id,
        kind=PayeeKind(payee.kind),
        display_name=payee.display_name,
        normalized_name=payee.normalized_name,
        status=PayeeStatus(payee.status),
        payment_method=PaymentMethod(payee.payment_method),
        default_category=PaymentCategory(payee.default_category)
        if payee.default_category
        else None,
        currency=payee.currency,
        per_payment_max_usd=payee.per_payment_max_usd,
        monthly_budget_usd=payee.monthly_budget_usd,
        agreed_amount_usd=payee.agreed_amount_usd,
        agreed_tolerance_pct=payee.agreed_tolerance_pct,
        attributes=dict(payee.attributes),
        version=payee.version,
    )


def _to_identifier(identifier: PayeeIdentifierRow) -> PayeeIdentifierRecord:
    return PayeeIdentifierRecord(
        identifier_id=identifier.id,
        payee_id=identifier.payee_id,
        kind=IdentifierKind(identifier.kind),
        normalized_value=identifier.normalized_value,
        raw_value=identifier.raw_value,
    )


def _to_blacklist_entry(entry: BlacklistEntryRow) -> BlacklistEntryRecord:
    return BlacklistEntryRecord(
        entry_id=entry.id,
        owner_id=entry.owner_id,
        kind=IdentifierKind(entry.kind),
        normalized_value=entry.normalized_value,
        reason=entry.reason,
        created_at=entry.created_at,
    )
