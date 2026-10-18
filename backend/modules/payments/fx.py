import re
from datetime import date

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


def current_period(today: date) -> str:
    return f"{today:%Y-%m}"
