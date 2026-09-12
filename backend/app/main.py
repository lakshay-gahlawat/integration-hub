from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import RateLimitMiddleware
from app.routers import activity, auth, integrations, sync_jobs, webhooks

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Integration Hub -- a portfolio-scale integration platform demonstrating "
        "OAuth, webhooks, idempotency, retries, and background sync against "
        "real external APIs (GitHub and Slack)."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never leak stack traces or internals to the client; log server-side
    # with full detail instead.
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_error", "message": "Something went wrong. Please try again."},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "request_error", "message": exc.detail},
    )


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "service": settings.APP_NAME}


app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(integrations.router, prefix=settings.API_PREFIX)
app.include_router(webhooks.router, prefix=settings.API_PREFIX)
app.include_router(sync_jobs.router, prefix=settings.API_PREFIX)
app.include_router(activity.router, prefix=settings.API_PREFIX)
