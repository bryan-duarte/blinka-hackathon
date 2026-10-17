from typing import TYPE_CHECKING

from contracts.payment_candidates import ExpenseReading

if TYPE_CHECKING:
    from modules.document_vision.textract import TextractExpenseReader


class DocumentVisionClient:
    def __init__(self, reader: "TextractExpenseReader") -> None:
        self._reader = reader

    async def read_expense(self, document: bytes) -> ExpenseReading:
        return await self._reader.read_expense(document)
