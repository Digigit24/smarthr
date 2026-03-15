"""Custom Django admin authentication backend via SuperAdmin API.

When a user logs in to /admin/, Django calls authenticate() on each backend
in AUTHENTICATION_BACKENDS. This backend proxies the credentials to the
SuperAdmin API (https://admin.celiyo.com/api/auth/login/) and, on success,
finds or creates a local Django User with is_staff=True so admin sessions work.

No local password is ever stored — set_unusable_password() is called every time.
"""
import logging

import requests
from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()


class SuperAdminAPIBackend:
    """Authenticate against the Celiyo SuperAdmin API for Django admin access."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        username: treated as email address (Django admin form sends it as 'username').
        password: plain-text password entered in the admin form.
        """
        if not username or not password:
            return None

        superadmin_url = getattr(
            settings, "SUPERADMIN_URL", "https://admin.celiyo.com"
        ).rstrip("/")
        login_url = f"{superadmin_url}/api/auth/login/"

        try:
            resp = requests.post(
                login_url,
                json={"email": username, "password": password},
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
        except requests.ConnectionError as exc:
            logger.error(f"Cannot connect to SuperAdmin API at {login_url}: {exc}")
            return None
        except requests.Timeout:
            logger.error(f"SuperAdmin API timed out after 10s")
            return None
        except requests.RequestException as exc:
            logger.error(f"SuperAdmin API request failed: {exc}")
            return None

        if not resp.ok:
            logger.warning(
                f"SuperAdmin API login rejected for {username!r}: "
                f"HTTP {resp.status_code}"
            )
            return None

        try:
            data = resp.json()
        except Exception:
            logger.error("SuperAdmin API returned non-JSON response")
            return None

        user_data = data.get("user", {})
        tokens = data.get("tokens", {})

        if not user_data.get("is_active", True):
            logger.warning(f"SuperAdmin user {username!r} is not active")
            return None

        email = user_data.get("email") or username
        first_name = user_data.get("first_name") or ""
        last_name = user_data.get("last_name") or ""
        is_super_admin = user_data.get("is_super_admin", False)

        # Find or create the local Django User (username == email for uniqueness)
        user, created = User.objects.get_or_create(
            username=email,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "is_staff": True,
                "is_superuser": is_super_admin,
                "is_active": True,
            },
        )

        if not created:
            # Sync fields that may have changed on the SuperAdmin side
            dirty = []
            if user.email != email:
                user.email = email
                dirty.append("email")
            if user.first_name != first_name:
                user.first_name = first_name
                dirty.append("first_name")
            if user.last_name != last_name:
                user.last_name = last_name
                dirty.append("last_name")
            if not user.is_staff:
                user.is_staff = True
                dirty.append("is_staff")
            if is_super_admin and not user.is_superuser:
                user.is_superuser = True
                dirty.append("is_superuser")
            if not user.is_active:
                user.is_active = True
                dirty.append("is_active")
            if dirty:
                user.save(update_fields=dirty)

        # Never allow local password login — auth always goes through SuperAdmin API
        user.set_unusable_password()
        user.save(update_fields=["password"])

        # Stash the SuperAdmin JWT tokens in the session for potential downstream use
        if request is not None and hasattr(request, "session"):
            request.session["superadmin_access_token"] = tokens.get("access", "")
            request.session["superadmin_refresh_token"] = tokens.get("refresh", "")
            request.session["superadmin_tenant_id"] = user_data.get("tenant", "")
            request.session["superadmin_tenant_name"] = user_data.get("tenant_name", "")

        logger.info(
            f"SuperAdmin login successful for {email!r} "
            f"(is_super_admin={is_super_admin}, created={created})"
        )
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
