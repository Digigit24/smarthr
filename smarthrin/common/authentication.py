"""DRF authentication class — reads attributes set by JWT middleware."""
from typing import Optional, Tuple

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from .tenant_user import TenantUser


class JWTRequestAuthentication(BaseAuthentication):
    """
    DRF authentication class.

    Reads JWT payload attributes already set by JWTAuthenticationMiddleware
    and constructs a TenantUser object as request.user.
    """

    def authenticate(self, request: Request) -> Optional[Tuple[TenantUser, None]]:
        payload = getattr(request, "jwt_payload", None)
        if payload is None:
            # Public path or middleware skipped — no user
            return None

        try:
            user = TenantUser(payload)
        except Exception as exc:
            raise AuthenticationFailed(f"Failed to construct user from JWT: {exc}") from exc

        return (user, None)

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"
