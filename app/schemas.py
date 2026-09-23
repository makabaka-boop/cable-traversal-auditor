"""Pydantic request/response models and batch validation rules.

Validation failures (structural problems, unknown connectors, duplicate
jumper ids, ...) are raised as Pydantic errors, which FastAPI serialises as
HTTP 422 for the whole batch -- a single bad jumper rejects nothing
selectively.
"""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_CONNECTORS = 300
MAX_JUMPERS = 3000
MAX_NAME_LEN = 64


class JumperSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=MAX_NAME_LEN)
    endpoints: list[str] = Field(
        min_length=2,
        max_length=2,
        description="Undirected pair [a, b]; [x, x] is a self-loop.",
    )


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connectors: list[str] = Field(min_length=1, max_length=MAX_CONNECTORS)
    jumpers: list[JumperSpec] = Field(min_length=1, max_length=MAX_JUMPERS)

    @field_validator("connectors")
    @classmethod
    def connectors_are_ascii_and_unique(cls, value: list[str]) -> list[str]:
        for name in value:
            if not isinstance(name, str) or not name:
                raise ValueError("connector names must be non-empty strings")
            if len(name) > MAX_NAME_LEN:
                raise ValueError(
                    f"connector name longer than {MAX_NAME_LEN} characters"
                )
            if not name.isascii():
                raise ValueError(f"connector {name!r} is not ASCII")
        if len(set(value)) != len(value):
            raise ValueError("connector names must be unique")
        return value

    @model_validator(mode="after")
    def jumper_ids_known_and_unique(self) -> VerifyRequest:
        known = set(self.connectors)
        seen: set[str] = set()
        for jumper in self.jumpers:
            if jumper.id in seen:
                raise ValueError(f"duplicate jumper id: {jumper.id!r}")
            seen.add(jumper.id)
            for endpoint in jumper.endpoints:
                if endpoint not in known:
                    raise ValueError(
                        f"jumper {jumper.id!r} references unknown connector "
                        f"{endpoint!r}"
                    )
        return self


class WalkResponse(BaseModel):
    status: Literal["OK"] = "OK"
    start: str
    connectors: list[str]
    jumpers: list[str]


class DisconnectedResponse(BaseModel):
    status: Literal["DISCONNECTED"] = "DISCONNECTED"
    components: int = Field(ge=2)
    witness: list[str] = Field(min_length=2, max_length=2)


class OddDegreeResponse(BaseModel):
    status: Literal["ODD_DEGREE"] = "ODD_DEGREE"
    odd_connectors: list[str]


VerifyResponse = Union[WalkResponse, DisconnectedResponse, OddDegreeResponse]
