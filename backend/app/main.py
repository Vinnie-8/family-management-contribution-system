"""
Application entry point: creates the FastAPI app, configures middleware,
translates domain errors into HTTP responses, and mounts the routers.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.models  # noqa: F401  (loads every model so SQLAlchemy relationships always resolve)
from app.config import settings
from app.core.exceptions import (
    BusinessRuleError,
    ContactRequiredError,
    DomainError,
    DuplicateMemberError,
    InactiveMemberError,
    InvalidActivationTokenError,
    InvalidCredentialsError,
    InvalidRegistrationCodeError,
    NotFoundError,
    PermissionDeniedError,
)
from app.routers import auth ,members,households,financial_years,campaigns
# adjust to your actual router modules

app = FastAPI(title="Family Members API", version="1.0.0")

# --- Middleware -------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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
    PermissionDeniedError,
    _handler(403, "You do not have permission to perform this action"),
)
app.add_exception_handler(
    InvalidActivationTokenError,
    _handler(400, "This link is invalid or has expired"),
)
app.add_exception_handler(
    InvalidRegistrationCodeError,
    _handler(400, "This registration code is invalid or has expired"),
)
app.add_exception_handler(
    ContactRequiredError,
    _handler(400, "A phone number or email is required"),
)
app.add_exception_handler(NotFoundError, _handler(404, "Not found"))
app.add_exception_handler(
    DuplicateMemberError,
    _handler(409, "A member with this phone, email or ID number already exists"),
)
app.add_exception_handler(
    BusinessRuleError,
    _handler(422, "Request breaks a family rule"),
)
# Fallback for any other DomainError subclass you add later
app.add_exception_handler(DomainError, _handler(400, "Request could not be processed"))


# --- Routers ---------------------------------------------------------------
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(members.router, prefix="/members", tags=["members"])
app.include_router(households.router, prefix="/households", tags=["households"])
app.include_router(financial_years.router, prefix="/financial-years", tags=["financial years"])
app.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])


# --- Health check (public, no auth) -------------------------------------------
@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok"}