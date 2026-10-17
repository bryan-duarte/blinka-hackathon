class InvoiceIngestorError(Exception):
    pass


class InvoiceParseError(InvoiceIngestorError):
    def __init__(self, reason: str = "", methods_tried: tuple[str, ...] = ()) -> None:
        super().__init__(reason)
        self.methods_tried = list(methods_tried)


class BillClassificationError(InvoiceIngestorError):
    pass
