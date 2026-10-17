from dataclasses import dataclass
from decimal import Decimal

from contracts.payment_policy import PayeeRecord, PaymentCategory, PaymentPolicy

GLOBAL_SCOPE = "global"
CATEGORY_SCOPE_PREFIX = "category:"
PAYEE_SCOPE_PREFIX = "payee:"


@dataclass(frozen=True)
class BudgetCharge:
    scope: str
    limit_usd: Decimal


def budget_charges(
    policy: PaymentPolicy, payee: PayeeRecord | None, category: PaymentCategory | None
) -> list[BudgetCharge]:
    charges = [BudgetCharge(GLOBAL_SCOPE, policy.monthly_budget_usd)]
    category_budget = policy.category_monthly_budgets_usd.get(category) if category else None
    if category_budget is not None:
        charges.append(BudgetCharge(f"{CATEGORY_SCOPE_PREFIX}{category}", category_budget))
    if payee is not None and payee.monthly_budget_usd is not None:
        charges.append(
            BudgetCharge(f"{PAYEE_SCOPE_PREFIX}{payee.payee_id}", payee.monthly_budget_usd)
        )
    return sorted(charges, key=lambda charge: charge.scope)


def describe_scope(scope: str, payee: PayeeRecord | None) -> str:
    if scope.startswith(CATEGORY_SCOPE_PREFIX):
        return f"mensual de {scope.removeprefix(CATEGORY_SCOPE_PREFIX)}"
    if scope.startswith(PAYEE_SCOPE_PREFIX) and payee is not None:
        return f"mensual de {payee.display_name}"
    return "mensual global"
