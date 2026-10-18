from datetime import date
from decimal import Decimal

STATIC_RATES_REFERENCE_DATE = date(2026, 10, 17)

STATIC_USD_PER_UNIT: dict[str, Decimal] = {
    "USD": Decimal("1"),
    "CLP": Decimal("0.001018"),
    "CLF": Decimal("40.23"),
    "EUR": Decimal("1.124"),
    "MXN": Decimal("0.05416"),
    "COP": Decimal("0.000314"),
    "BRL": Decimal("0.1965"),
    "PEN": Decimal("0.2911"),
    "ARS": Decimal("0.00066"),
    "GBP": Decimal("1.332"),
}
