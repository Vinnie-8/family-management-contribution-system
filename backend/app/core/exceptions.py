"""
Domain exceptions — raised by services, translated to HTTP responses in
main.py's exception handlers. Keeping services free of `HTTPException`
means the same service functions could be reused outside a web request
(a CLI script, a background job) without dragging FastAPI along.
"""


class DomainError(Exception):
    """Base class for all application-level errors."""


class InvalidCredentialsError(DomainError):
    """Wrong phone/email or password. Deliberately generic (see auth_service) —
    never reveals whether the identifier or the password was the wrong part."""


class InactiveMemberError(DomainError):
    """Member exists but is_active=False (FR1.6 universal gate)."""


class TempPasswordExpiredError(DomainError):
    """FR1.5 — temp password's expiry has passed; must request a new one."""


class MustChangePasswordError(DomainError):
    """FR1.4 — login succeeded but member must change password before anything else.
    Not really an 'error' in the failure sense — it's a signal the router uses to
    return a restricted token/response rather than a full session."""


class PermissionDeniedError(DomainError):
    """Member is authenticated but lacks the required role for this action."""


class DuplicateMemberError(DomainError):
    """Onboarding conflict — duplicate phone/email within the same family (FR1.2)."""