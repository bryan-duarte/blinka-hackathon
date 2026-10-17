class PaymentsError(Exception):
    pass


class RunNotFoundError(PaymentsError):
    pass


class RunTriggerError(PaymentsError):
    pass
