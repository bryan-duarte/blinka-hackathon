import re

NON_IDENTIFIER_CHARACTERS = re.compile(r"[^0-9A-Za-z]")


def canonical_identifier(value: str) -> str:
    return NON_IDENTIFIER_CHARACTERS.sub("", value).upper()
