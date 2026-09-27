"""Application setup, health reporting, and shared HTTP error responses."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routes.diaries import router as diaries_router
from app.routes.notes import router as notes_router
from app.routes.stats import router as stats_router
from app.reporting import report
from app.storage import redis_client

app = FastAPI(title="Cardinal Notes API")
app.include_router(notes_router)
app.include_router(diaries_router)
app.include_router(stats_router)


@app.get("/health")
def health() -> dict[str, str]:
    redis_client.ping()
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def invalid_request(_: Request, error: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": "invalid request", "details": error.errors()})


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
    if error.status_code == 404:
        return JSONResponse(status_code=404, content={"error": "not found"})
    return JSONResponse(status_code=error.status_code, content={"error": str(error.detail)})


@app.exception_handler(Exception)
async def unhandled_error(request: Request, error: Exception) -> JSONResponse:
    report(error, request.method, request.url.path)
    return JSONResponse(status_code=500, content={"error": "internal error"})
