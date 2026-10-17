class InvoiceIngestorError(Exception):
    pass


class InvoiceParseError(InvoiceIngestorError):
    pass


class BillClassificationError(InvoiceIngestorError):
    pass
