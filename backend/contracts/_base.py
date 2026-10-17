from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
