from typing import Literal

from contracts._base import StrictModel

ModelKind = Literal["main", "payments"]


class ModelSpec(StrictModel):
    kind: ModelKind
