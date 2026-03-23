"""Redis cache layer for voice agent lists to avoid hitting the Voice AI API on every render."""
import hashlib
import json
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache TTL in seconds
VOICE_AGENT_CACHE_TTL = 60


def _cache_key(tenant_id: str, **params) -> str:
    """Build a deterministic cache key from tenant + query params + version."""
    version_key = f"voice_agents_version:{tenant_id}"
    version = cache.get(version_key, 0)
    param_str = json.dumps({k: v for k, v in sorted(params.items()) if v is not None}, sort_keys=True)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:12]
    return f"voice_agents:v{version}:{tenant_id}:{param_hash}"


def get_cached_agents(tenant_id: str, **params):
    """Return cached agent list or None if not cached."""
    key = _cache_key(tenant_id, **params)
    data = cache.get(key)
    if data is not None:
        logger.debug(f"Voice agent cache HIT: {key}")
    return data


def set_cached_agents(tenant_id: str, agents, **params) -> None:
    """Cache agent list with TTL."""
    key = _cache_key(tenant_id, **params)
    cache.set(key, agents, timeout=VOICE_AGENT_CACHE_TTL)
    logger.debug(f"Voice agent cache SET: {key} (ttl={VOICE_AGENT_CACHE_TTL}s)")


def invalidate_agent_cache(tenant_id: str) -> None:
    """Invalidate all cached agent lists for a tenant.

    Uses a versioning approach: bump a version counter so all existing
    keys become stale. This avoids scanning Redis for matching keys.
    """
    version_key = f"voice_agents_version:{tenant_id}"
    try:
        cache.incr(version_key)
    except ValueError:
        # Key doesn't exist yet
        cache.set(version_key, 1, timeout=None)
    except Exception as exc:
        # Redis may be down — log but don't crash the caller
        logger.warning(f"Failed to invalidate voice agent cache for tenant {tenant_id}: {exc}")
        return
    logger.info(f"Voice agent cache invalidated for tenant {tenant_id}")
