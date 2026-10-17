import secrets
from datetime import UTC, datetime

from langchain_core.tools import tool

from contracts.tools import RandomToken, SystemProfile

RANDOM_TOKEN_BYTES = 8
SYSTEM_PROFILE = SystemProfile(
    name="blinka",
    environment="diagnostics",
    version="0.1.0",
    capabilities=["chat", "invoice_ingestion", "payments"],
)


@tool("get_random_token")
async def get_random_token() -> dict:
    """Return a freshly generated random token and the UTC time it was generated."""
    random_token = RandomToken(
        token=secrets.token_hex(RANDOM_TOKEN_BYTES),
        generated_at=datetime.now(UTC).isoformat(),
    )
    return random_token.model_dump()


@tool("get_system_profile")
async def get_system_profile() -> dict:
    """Return the fixed profile of the Blinka system: name, environment, version, capabilities."""
    return SYSTEM_PROFILE.model_dump()
