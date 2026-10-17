import re
from collections.abc import Callable

from core.identifiers import canonical_identifier

MODULO_11 = 11
MODULO_97 = 97
DECIMAL_BASE = 10
CNPJ_ZERO_CHECK_THRESHOLD = 2
IBAN_CHECK_REMAINDER = 1
CLABE_LENGTH = 18
CLABE_WEIGHTS = (3, 7, 1)
CHILE_RUT_WEIGHTS = (2, 3, 4, 5, 6, 7)
CNPJ_FIRST_WEIGHTS = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
CNPJ_SECOND_WEIGHTS = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
GREEK_VAT_PREFIX = "EL"
GREECE = "GR"
MEXICO_GENERIC_FOREIGN_RFC = "XEXX010101000"

EU_VAT_COUNTRIES = frozenset(
    {
        "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU",
        "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK",
    }
)  # fmt: skip
BIC_COUNTRIES = EU_VAT_COUNTRIES | frozenset(
    {
        "AR", "AU", "BO", "BR", "CA", "CH", "CL", "CN", "CO", "CR", "DO", "EC", "GB", "GT",
        "HK", "IN", "JP", "MX", "NO", "PA", "PE", "PY", "SA", "SG", "SV", "TR", "US", "UY",
    }
)  # fmt: skip

IBAN_PATTERN = re.compile(r"(?P<country>[A-Z]{2})\d{2}[A-Z0-9]{11,30}")
BIC_PATTERN = re.compile(r"[A-Z]{4}(?P<country>[A-Z]{2})[A-Z0-9]{2}(?:[A-Z0-9]{3})?")
CLABE_PATTERN = re.compile(rf"\d{{{CLABE_LENGTH}}}")
EU_VAT_PATTERN = re.compile(r"(?P<prefix>[A-Z]{2})[A-Z0-9]{8,12}")

TAX_ID_SHAPES: dict[str, re.Pattern[str]] = {
    "MX": re.compile(r"[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}"),
    "CL": re.compile(r"\d{7,8}[0-9K]"),
    "CO": re.compile(r"\d{8,10}"),
    "PE": re.compile(r"(10|15|16|17|20)\d{9}"),
    "EC": re.compile(r"\d{10}001"),
    "BR": re.compile(r"\d{14}|\d{11}"),
    "AR": re.compile(r"(20|23|24|27|30|33|34)\d{9}"),
    "UY": re.compile(r"\d{12}"),
    "CR": re.compile(r"\d{9,12}"),
    "GT": re.compile(r"\d{4,12}[0-9K]"),
    "PY": re.compile(r"\d{5,9}"),
    "DO": re.compile(r"\d{9}|\d{11}"),
    "PA": re.compile(r"[0-9A-Z]{5,20}"),
    "BO": re.compile(r"\d{6,13}"),
    "US": re.compile(r"\d{9}"),
    "SA": re.compile(r"3\d{13}3"),
    "TR": re.compile(r"\d{10,11}"),
    "IT": re.compile(r"(IT)?\d{11}"),
    "ES": re.compile(r"(ES)?[A-Z0-9]\d{7}[A-Z0-9]"),
    "PL": re.compile(r"(PL)?\d{10}"),
    "HU": re.compile(r"(HU)?\d{8}(\d{3})?"),
    "GR": re.compile(r"(EL|GR)?\d{9}"),
    "PT": re.compile(r"(PT)?\d{9}"),
    "DE": re.compile(r"(DE)?\d{9}|\d{10,13}"),
    "FR": re.compile(r"(FR)?[A-Z0-9]{2}\d{9}"),
    "NL": re.compile(r"(NL)?\d{9}B\d{2}|\d{8}"),
    "GB": re.compile(r"(GB)?(\d{9}|\d{12})"),
}


def tax_id_fits_country(tax_id: str | None, country: str | None) -> bool | None:
    if not tax_id or not country:
        return None
    normalized_tax_id = canonical_identifier(tax_id)
    country_code = country.upper()
    if country_code == "MX" and normalized_tax_id == MEXICO_GENERIC_FOREIGN_RFC:
        return False
    shape = TAX_ID_SHAPES.get(country_code)
    if shape is None:
        return None
    return (
        shape.fullmatch(normalized_tax_id) is not None
        or _eu_vat_country(normalized_tax_id) == country_code
    )


def infer_tax_id_country(tax_id: str | None) -> str | None:
    if not tax_id:
        return None
    normalized_tax_id = canonical_identifier(tax_id)
    for country, is_valid_tax_id in UNAMBIGUOUS_TAX_ID_CHECKS:
        if is_valid_tax_id(tax_id, normalized_tax_id):
            return country
    return _eu_vat_country(normalized_tax_id)


def bank_account_country(bank_account: str | None) -> str | None:
    if not bank_account:
        return None
    normalized_account = canonical_identifier(bank_account)
    if _is_valid_iban(normalized_account):
        return normalized_account[:2]
    if _is_valid_clabe(normalized_account):
        return "MX"
    bic_match = BIC_PATTERN.fullmatch(normalized_account)
    if bic_match and bic_match.group("country") in BIC_COUNTRIES:
        return bic_match.group("country")
    return None


def _is_mexican_rfc(raw_tax_id: str, normalized_tax_id: str) -> bool:
    is_generic_rfc = normalized_tax_id == MEXICO_GENERIC_FOREIGN_RFC
    return not is_generic_rfc and TAX_ID_SHAPES["MX"].fullmatch(normalized_tax_id) is not None


def _is_chilean_rut(raw_tax_id: str, normalized_tax_id: str) -> bool:
    has_check_digit_separator = "-" in raw_tax_id
    if not has_check_digit_separator or not TAX_ID_SHAPES["CL"].fullmatch(normalized_tax_id):
        return False
    body, check_digit = normalized_tax_id[:-1], normalized_tax_id[-1]
    weighted_sum = sum(
        int(digit) * CHILE_RUT_WEIGHTS[index % len(CHILE_RUT_WEIGHTS)]
        for index, digit in enumerate(reversed(body))
    )
    expected = MODULO_11 - weighted_sum % MODULO_11
    expected_digit = {MODULO_11: "0", MODULO_11 - 1: "K"}.get(expected, str(expected))
    return check_digit == expected_digit


def _is_brazilian_cnpj(raw_tax_id: str, normalized_tax_id: str) -> bool:
    if not re.fullmatch(r"\d{14}", normalized_tax_id):
        return False
    digits = [int(digit) for digit in normalized_tax_id]
    first_check = _cnpj_check_digit(digits[:12], CNPJ_FIRST_WEIGHTS)
    second_check = _cnpj_check_digit([*digits[:12], first_check], CNPJ_SECOND_WEIGHTS)
    return digits[12:] == [first_check, second_check]


def _cnpj_check_digit(digits: list[int], weights: tuple[int, ...]) -> int:
    remainder = (
        sum(digit * weight for digit, weight in zip(digits, weights, strict=True)) % MODULO_11
    )
    return 0 if remainder < CNPJ_ZERO_CHECK_THRESHOLD else MODULO_11 - remainder


def _is_us_ein(raw_tax_id: str, normalized_tax_id: str) -> bool:
    return re.fullmatch(r"\s*\d{2}-\d{7}\s*", raw_tax_id) is not None


def _is_ecuadorian_ruc(raw_tax_id: str, normalized_tax_id: str) -> bool:
    return TAX_ID_SHAPES["EC"].fullmatch(normalized_tax_id) is not None


def _is_saudi_vat(raw_tax_id: str, normalized_tax_id: str) -> bool:
    return TAX_ID_SHAPES["SA"].fullmatch(normalized_tax_id) is not None


UNAMBIGUOUS_TAX_ID_CHECKS: tuple[tuple[str, Callable[[str, str], bool]], ...] = (
    ("MX", _is_mexican_rfc),
    ("CL", _is_chilean_rut),
    ("BR", _is_brazilian_cnpj),
    ("US", _is_us_ein),
    ("EC", _is_ecuadorian_ruc),
    ("SA", _is_saudi_vat),
)


def _eu_vat_country(normalized_tax_id: str) -> str | None:
    vat_match = EU_VAT_PATTERN.fullmatch(normalized_tax_id)
    if vat_match is None:
        return None
    prefix = vat_match.group("prefix")
    country = GREECE if prefix == GREEK_VAT_PREFIX else prefix
    return country if country in EU_VAT_COUNTRIES else None


def _is_valid_iban(normalized_account: str) -> bool:
    if IBAN_PATTERN.fullmatch(normalized_account) is None:
        return False
    rearranged = normalized_account[4:] + normalized_account[:4]
    numeric_account = "".join(str(int(character, 36)) for character in rearranged)
    return int(numeric_account) % MODULO_97 == IBAN_CHECK_REMAINDER


def _is_valid_clabe(normalized_account: str) -> bool:
    if CLABE_PATTERN.fullmatch(normalized_account) is None:
        return False
    weighted_sum = sum(
        int(digit) * CLABE_WEIGHTS[index % len(CLABE_WEIGHTS)]
        for index, digit in enumerate(normalized_account[:-1])
    )
    expected_check_digit = (DECIMAL_BASE - weighted_sum % DECIMAL_BASE) % DECIMAL_BASE
    return int(normalized_account[-1]) == expected_check_digit
