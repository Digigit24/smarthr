"""TenantUser — in-memory user object constructed from JWT payload."""
from typing import Any


class TenantUser:
    """
    Represents an authenticated user constructed from a decoded JWT payload.
    This is NOT a Django model — it lives only in memory for the duration of a request.
    """

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.id: str = payload.get("user_id", "")
        self.email: str = payload.get("email", "")
        self.first_name: str = payload.get("first_name", "")
        self.last_name: str = payload.get("last_name", "")
        self.tenant_id: str = payload.get("tenant_id", "")
        self.tenant_slug: str = payload.get("tenant_slug", "")
        self.is_super_admin: bool = payload.get("is_super_admin", False)
        self.permissions: dict[str, Any] = payload.get("permissions", {})
        self.enabled_modules: list[str] = payload.get("enabled_modules", [])

    # ------------------------------------------------------------------
    # Django auth interface compatibility
    # ------------------------------------------------------------------

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    @property
    def pk(self) -> str:
        return self.id

    def __str__(self) -> str:
        return f"{self.email} ({self.tenant_slug})"

    # ------------------------------------------------------------------
    # Permission helpers
    # ------------------------------------------------------------------

    def get_permission(self, key: str) -> Any:
        """
        Resolve a dot-separated permission key like 'smarthrin.jobs.view'.
        Returns the value: false | true | "all" | "own" | "team"
        """
        parts = key.split(".")
        node: Any = self.permissions
        for part in parts:
            if not isinstance(node, dict):
                return False
            node = node.get(part, False)
        return node

    def has_perm(self, key: str) -> bool:
        """Return True if the permission value is truthy."""
        if self.is_super_admin:
            return True
        value = self.get_permission(key)
        return bool(value)

    def has_module_access(self, module_name: str) -> bool:
        """Return True if the given module is in the tenant's enabled modules."""
        return module_name in self.enabled_modules
