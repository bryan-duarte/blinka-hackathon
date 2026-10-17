class BillsError(Exception):
    pass


class BillMissingError(BillsError):
    pass


class BillStateConflictError(BillsError):
    pass


class BillSourceMissingError(BillsError):
    pass


class InvalidBillTransitionError(BillsError):
    pass
