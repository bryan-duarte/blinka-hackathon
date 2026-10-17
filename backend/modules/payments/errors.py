class PaymentsError(Exception):
    pass


class RunNotFoundError(PaymentsError):
    pass


class RunTriggerError(PaymentsError):
    pass


class BudgetExhaustedError(PaymentsError):
    def __init__(self, scope: str) -> None:
        super().__init__(scope)
        self.scope = scope


class PaymentStateError(PaymentsError):
    pass


class BillNotReviewableError(PaymentsError):
    pass


class DecisionMissingError(PaymentsError):
    pass
