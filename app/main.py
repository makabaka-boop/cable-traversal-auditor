from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .euler import Jumper, verify
from .schemas import VerifyRequest, VerifyResponse

app = FastAPI(
    title="Temporary Exhibition Cabling Verification API",
    version="1.0.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/verify", response_model=VerifyResponse)
def verify_cabling(request: VerifyRequest):
    result = verify(
        request.connectors,
        [Jumper(id=jumper.id, u=jumper.u, v=jumper.v) for jumper in request.jumpers],
    )
    return JSONResponse(result)
