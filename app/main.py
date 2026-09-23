"""FastAPI application: pure back-end JSON verification API."""

from __future__ import annotations

from fastapi import FastAPI

from app.euler import Disconnected, Jumper, OddDegree, Walk, find_walk
from app.schemas import (
    DisconnectedResponse,
    OddDegreeResponse,
    VerifyRequest,
    VerifyResponse,
    WalkResponse,
)

app = FastAPI(
    title="Patch-Bay Walk Verifier",
    version="1.0.0",
    summary=(
        "Check whether every test jumper can be traversed exactly once and, "
        "if so, return the deterministic minimum complete walk."
    ),
)


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    return {"status": "up"}


@app.post(
    "/api/v1/walks/verify",
    response_model=VerifyResponse,
    tags=["verification"],
    summary="Verify one connector/jumper batch",
)
def verify_walk(request: VerifyRequest) -> VerifyResponse:
    jumpers = [
        Jumper(id=item.id, a=item.endpoints[0], b=item.endpoints[1])
        for item in request.jumpers
    ]
    result = find_walk(request.connectors, jumpers)

    if isinstance(result, Walk):
        return WalkResponse(
            start=result.start,
            connectors=list(result.connectors),
            jumpers=list(result.jumpers),
        )
    if isinstance(result, Disconnected):
        return DisconnectedResponse(
            components=result.components,
            witness=list(result.witness),
        )
    assert isinstance(result, OddDegree)
    return OddDegreeResponse(odd_connectors=list(result.odd_connectors))
