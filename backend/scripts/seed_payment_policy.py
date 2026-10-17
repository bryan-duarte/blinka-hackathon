import argparse
import asyncio
import sys
from decimal import Decimal

from contracts.auth import CurrentUser
from contracts.payment_policy import (
    BlacklistEntryCreate,
    IdentifierKind,
    PayeeCreate,
    PayeeIdentifierCreate,
    PayeeKind,
    PaymentCategory,
    PaymentMethod,
    PaymentPolicyUpdate,
)
from core.config import Settings
from core.db import create_engine_and_sessionmaker
from modules.auth import UsersRepository
from modules.payment_policy import (
    PayeeNameTakenError,
    PaymentPolicyRepository,
    PaymentPolicyService,
    PolicyMissingError,
)

DEMO_POLICY = PaymentPolicyUpdate(
    hard_cap_per_payment_usd=Decimal("5000"),
    auto_pay_max_usd=Decimal("1000"),
    monthly_budget_usd=Decimal("12000"),
    category_monthly_budgets_usd={
        PaymentCategory.CLOUD: Decimal("3000"),
        PaymentCategory.SAAS: Decimal("1500"),
        PaymentCategory.CONTRACTOR: Decimal("6000"),
        PaymentCategory.PROFESSIONAL_SERVICES: Decimal("2500"),
    },
    allowed_categories=[
        PaymentCategory.CLOUD,
        PaymentCategory.SAAS,
        PaymentCategory.CONTRACTOR,
        PaymentCategory.PROFESSIONAL_SERVICES,
        PaymentCategory.UTILITIES,
    ],
    allowed_currencies=["USD", "CLP", "CLF", "MXN", "COP"],
)

DEMO_PAYEES = (
    PayeeCreate(
        kind=PayeeKind.SERVICE,
        display_name="Amazon Web Services",
        payment_method=PaymentMethod.CARD_ON_FILE,
        default_category=PaymentCategory.CLOUD,
        currency="USD",
        identifiers=[
            PayeeIdentifierCreate(kind=IdentifierKind.DOMAIN, value="aws.amazon.com"),
            PayeeIdentifierCreate(kind=IdentifierKind.DOMAIN, value="amazon.com"),
            PayeeIdentifierCreate(kind=IdentifierKind.SERVICE_ACCOUNT_ID, value="123456789012"),
            PayeeIdentifierCreate(kind=IdentifierKind.ALIAS, value="aws"),
        ],
    ),
    PayeeCreate(
        kind=PayeeKind.SERVICE,
        display_name="ACME Cloud",
        payment_method=PaymentMethod.BANK_TRANSFER,
        default_category=PaymentCategory.SAAS,
        currency="USD",
        agreed_amount_usd=Decimal("120"),
        agreed_tolerance_pct=Decimal("5"),
        identifiers=[
            PayeeIdentifierCreate(kind=IdentifierKind.DOMAIN, value="acmecloud.io"),
            PayeeIdentifierCreate(kind=IdentifierKind.BANK_ACCOUNT, value="000123456789"),
        ],
    ),
    PayeeCreate(
        kind=PayeeKind.COMPANY,
        display_name="Servicios Integrales del Sur SpA",
        payment_method=PaymentMethod.BANK_TRANSFER,
        default_category=PaymentCategory.PROFESSIONAL_SERVICES,
        currency="CLP",
        identifiers=[
            PayeeIdentifierCreate(kind=IdentifierKind.TAX_ID, value="76.543.210-K"),
            PayeeIdentifierCreate(kind=IdentifierKind.BANK_ACCOUNT, value="CL-001-2233445566"),
            PayeeIdentifierCreate(kind=IdentifierKind.EMAIL, value="facturacion@sisur.cl"),
        ],
    ),
    PayeeCreate(
        kind=PayeeKind.PERSON,
        display_name="María José Pérez",
        payment_method=PaymentMethod.BANK_TRANSFER,
        default_category=PaymentCategory.CONTRACTOR,
        currency="USD",
        monthly_budget_usd=Decimal("1500"),
        agreed_amount_usd=Decimal("900"),
        agreed_tolerance_pct=Decimal("0"),
        identifiers=[
            PayeeIdentifierCreate(kind=IdentifierKind.TAX_ID, value="15234567-8"),
            PayeeIdentifierCreate(kind=IdentifierKind.BANK_ACCOUNT, value="CL-BE-99887766"),
        ],
    ),
)

DEMO_BLACKLIST = (
    BlacklistEntryCreate(
        kind=IdentifierKind.BANK_ACCOUNT, value="US-CHASE-55554444", reason="cuenta reportada"
    ),
    BlacklistEntryCreate(
        kind=IdentifierKind.DOMAIN, value="amaz0n-billing.com", reason="dominio de phishing"
    ),
    BlacklistEntryCreate(
        kind=IdentifierKind.ALIAS, value="Proveedor Fantasma", reason="proveedor inexistente"
    ),
)


async def seed(email: str) -> int:
    settings = Settings()
    engine, sessionmaker = create_engine_and_sessionmaker(settings.product_database_url)
    try:
        user = await UsersRepository(sessionmaker).get_by_email(email)
        if user is None:
            print(f"No user registered with email {email}", file=sys.stderr)
            return 1
        owner = CurrentUser(user_id=user.user_id, email=user.email)
        service = PaymentPolicyService(PaymentPolicyRepository(sessionmaker))
        await _seed_policy(service, owner)
        await _seed_payees(service, owner)
        for entry in DEMO_BLACKLIST:
            await service.add_blacklist_entry(owner, entry)
        print(f"Seeded the demo payment policy for {email}")
        return 0
    finally:
        await engine.dispose()


async def _seed_policy(service: PaymentPolicyService, owner: CurrentUser) -> None:
    try:
        await service.get_policy(owner)
    except PolicyMissingError:
        await service.update_policy(owner, DEMO_POLICY)


async def _seed_payees(service: PaymentPolicyService, owner: CurrentUser) -> None:
    for payee in DEMO_PAYEES:
        try:
            await service.create_payee(owner, payee)
        except PayeeNameTakenError:
            print(f"Payee {payee.display_name} already exists; skipped")


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the demo payment policy for a user.")
    parser.add_argument("--email", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(seed(_parse_arguments().email)))
