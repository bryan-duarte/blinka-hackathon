import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

USD_CENTS = Decimal("0.01")

# TEMPORAL: dummy USD rates for the demo; replace with a dated FX source.
DUMMY_USD_PER_UNIT: dict[str, Decimal] = {
    "USD": Decimal("1"),
    "CLP": Decimal("0.00105"),
    "CLF": Decimal("41.50"),
    "EUR": Decimal("1.08"),
    "MXN": Decimal("0.055"),
    "COP": Decimal("0.00025"),
    "BRL": Decimal("0.18"),
}


EXPLICIT_CURRENCY_MARKERS: dict[str, tuple[str, ...]] = {
    "USD": ("us$", "dólar", "dolar", "dollar"),
    "CLP": ("clp$", "peso chileno", "pesos chilenos"),
    "CLF": ("uf", "unidad de fomento", "unidades de fomento"),
    "EUR": ("€", "euro"),
    "MXN": ("mx$", "peso mexicano", "pesos mexicanos"),
    "COP": ("col$", "peso colombiano", "pesos colombianos"),
    "BRL": ("r$", "real brasileño", "reales"),
}


def names_currency_explicitly(quote: str, currency: str) -> bool:
    code = currency.upper()
    folded_quote = quote.casefold()
    markers = (code.casefold(), *EXPLICIT_CURRENCY_MARKERS.get(code, ()))
    return any(re.search(_marker_pattern(marker), folded_quote) for marker in markers)


def _marker_pattern(marker: str) -> str:
    return rf"(?<![a-z]){re.escape(marker)}(?:e?s)?(?![a-z])"


def to_usd(amount: Decimal | None, currency: str | None) -> Decimal | None:
    if amount is None or currency is None:
        return None
    usd_per_unit = DUMMY_USD_PER_UNIT.get(currency.upper())
    if usd_per_unit is None:
        return None
    return (amount * usd_per_unit).quantize(USD_CENTS, rounding=ROUND_HALF_UP)


def current_period(today: date) -> str:
    return f"{today:%Y-%m}"
