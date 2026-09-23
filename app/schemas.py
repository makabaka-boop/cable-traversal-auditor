from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_VERTICES = 300
MAX_JUMPERS = 3000


class JumperIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    u: str
    v: str


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    connectors: list[str] = Field(..., min_length=1, max_length=MAX_VERTICES)
    jumpers: list[JumperIn] = Field(..., min_length=1, max_length=MAX_JUMPERS)

    @field_validator("connectors")
    @classmethod
    def validate_connectors(cls, connectors):
        non_ascii = [connector for connector in connectors if not connector.isascii()]
        if non_ascii:
            raise ValueError("connectors must contain only ASCII characters")
        return connectors

    @model_validator(mode="after")
    def validate_graph_references(self):
        if len(self.connectors) != len(set(self.connectors)):
            raise ValueError("connector values must be unique")

        seen_ids = set()
        duplicate_ids = set()
        unknown = []
        known = set(self.connectors)

        for jumper in self.jumpers:
            if jumper.id in seen_ids:
                duplicate_ids.add(jumper.id)
            seen_ids.add(jumper.id)

            if jumper.u not in known:
                unknown.append(f"{jumper.id}:u")
            if jumper.v not in known:
                unknown.append(f"{jumper.id}:v")

        errors = []
        if duplicate_ids:
            errors.append(
                "jumper ids must be unique: " + ", ".join(sorted(duplicate_ids))
            )
        if unknown:
            errors.append("unknown connectors at: " + ", ".join(unknown))
        if errors:
            raise ValueError("; ".join(errors))
        return self


class FeasibleResponse(BaseModel):
    status: Literal["FEASIBLE"]
    start: str
    connectors: list[str]
    jumper_ids: list[str]


class DisconnectedResponse(BaseModel):
    status: Literal["DISCONNECTED"]
    connector: str
    other_connector: str


class OddDegreeResponse(BaseModel):
    status: Literal["ODD_DEGREE"]
    connectors: list[str]


VerifyResponse = Union[FeasibleResponse, DisconnectedResponse, OddDegreeResponse]
