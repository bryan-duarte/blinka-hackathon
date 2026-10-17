class PaymentPolicyError(Exception):
    pass


class PolicyMissingError(PaymentPolicyError):
    pass


class PayeeMissingError(PaymentPolicyError):
    pass


class PayeeVersionConflictError(PaymentPolicyError):
    pass


class IdentifierTakenError(PaymentPolicyError):
    pass


class PayeeNameTakenError(PaymentPolicyError):
    pass


class BlacklistEntryMissingError(PaymentPolicyError):
    pass


class IdentifierMissingError(PaymentPolicyError):
    pass


class PayeeInUseError(PaymentPolicyError):
    pass
