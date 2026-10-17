from contracts._base import StrictModel


class RandomToken(StrictModel):
    token: str
    generated_at: str


class SystemProfile(StrictModel):
    name: str
    environment: str
    version: str
    capabilities: list[str]
