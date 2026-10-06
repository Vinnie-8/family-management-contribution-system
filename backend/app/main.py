"""
Application entry point: creates the FastAPI app, configures middleware,
translates domain errors into HTTP responses, and mounts the routers.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import (
    DomainError,
    DuplicateMemberError,
    InactiveMemberError,
    InvalidCredentialsError,
    MustChangePasswordError,
    PermissionDeniedError,
    TempPasswordExpiredError,
)
from app.routers import auth  # adjust to your actual router modules

app = FastAPI(title="Family Members API", version="1.0.0")

# --- Middleware -------------------------------------------------------------
# Needed only if a browser frontend on a different origin calls this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # e.g. ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Domain error -> HTTP response translation -------------------------------
def _handler(status_code: int, default_detail: str, headers: dict | None = None):
    async def handle(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={"detail": str(exc) or default_detail},
            headers=headers,
        )
    return handle


app.add_exception_handler(
    InvalidCredentialsError,
    _handler(401, "Invalid credentials", {"WWW-Authenticate": "Bearer"}),
)
app.add_exception_handler(InactiveMemberError, _handler(403, "Account is deactivated"))
app.add_exception_handler(
    TempPasswordExpiredError,
    _handler(401, "Temporary password has expired. Please request a new one."),
)
app.add_exception_handler(
    PermissionDeniedError,
    _handler(403, "You do not have permission to perform this action"),
)
app.add_exception_handler(
    DuplicateMemberError,
    _handler(409, "A member with this phone or email already exists"),
)
app.add_exception_handler(
    MustChangePasswordError,
    _handler(403, "Password change required before continuing"),
)
# Fallback for any other DomainError subclass you add later
app.add_exception_handler(DomainError, _handler(400, "Request could not be processed"))


# --- Routers ---------------------------------------------------------------
app.include_router(auth.router, prefix="/auth", tags=["auth"])

# --- Health check (public, no auth) -------------------------------------------
@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok"}