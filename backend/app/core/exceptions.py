"""
Domain exceptions: raised by services, translated to HTTP responses in
main.py's exception handlers. Services never import HTTPException.
"""


class DomainError(Exception):
    """Base class for all application-level errors."""


class InvalidCredentialsError(DomainError):
    """Wrong identifier or password. Deliberately generic."""


class InactiveMemberError(DomainError):
    """Member exists but is_active=False."""


class InvalidActivationTokenError(DomainError):
    """Activation link is unknown, used, expired, or its member can't activate.
    One message for all cases, so nothing leaks."""


class InvalidRegistrationCodeError(DomainError):
    """Registration code is unknown, used, or expired. Generic on purpose."""


class ContactRequiredError(DomainError):
    """A phone number or email is needed to finish activation."""


class PermissionDeniedError(DomainError):
    """Authenticated but lacks the required role for this action."""


class DuplicateMemberError(DomainError):
    """Phone, email or ID number is already registered (unique across the platform)."""


class NotFoundError(DomainError):
    """A household or member doesn't exist in the caller's family."""


class BusinessRuleError(DomainError):
    """A family rule was broken (for example, a household head must be an adult
    member of that household, or a minor needs a date of birth)."""