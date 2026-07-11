"""Tests for admin-privilege determination on the API-key auth path.

Admin access on the API-key path is decided by ``AuthManager._is_admin_user``:
the explicit ``auth.admin_users`` allowlist is the source of truth, and the
legacy ``-admin`` username-suffix convention is honoured only for backward
compatibility.
"""

import pytest

from mcprelay.auth import AuthManager
from mcprelay.config import MCPRelayConfig


def _manager(api_keys=None, admin_users=None, per_user_limits=None) -> AuthManager:
    config = MCPRelayConfig()
    config.auth.api_keys = api_keys or {}
    config.auth.admin_users = admin_users or []
    config.rate_limit.per_user_limits = per_user_limits or {}
    return AuthManager(config)


class TestIsAdminUser:
    def test_explicit_allowlist_grants_admin(self):
        mgr = _manager(admin_users=["alice"])
        assert mgr._is_admin_user("alice") is True

    def test_user_not_in_allowlist_is_not_admin(self):
        mgr = _manager(admin_users=["alice"])
        assert mgr._is_admin_user("bob") is False

    def test_plain_user_is_not_admin(self):
        assert _manager()._is_admin_user("regular-user") is False

    def test_legacy_suffix_still_grants_admin_for_backcompat(self):
        # The '-admin' convention must keep working so existing configs don't break.
        assert _manager()._is_admin_user("ops-admin") is True

    def test_allowlist_grants_admin_without_suffix(self):
        # The whole point: admin without needing a magic username suffix.
        mgr = _manager(admin_users=["plain-name"])
        assert mgr._is_admin_user("plain-name") is True


class TestApiKeyCacheAdminFlag:
    def test_api_key_for_allowlisted_user_is_admin(self):
        mgr = _manager(api_keys={"sk-1": "alice"}, admin_users=["alice"])
        ctx = mgr.api_key_cache[_hash("sk-1")]
        assert ctx["is_admin"] is True
        assert ctx["rate_limit_tier"] == "admin"

    def test_api_key_for_plain_user_is_not_admin(self):
        mgr = _manager(api_keys={"sk-2": "bob"})
        ctx = mgr.api_key_cache[_hash("sk-2")]
        assert ctx["is_admin"] is False
        assert ctx["rate_limit_tier"] == "default"

    def test_custom_rate_tier_takes_precedence(self):
        mgr = _manager(
            api_keys={"sk-3": "carol"},
            admin_users=["carol"],
            per_user_limits={"carol": 5},
        )
        ctx = mgr.api_key_cache[_hash("sk-3")]
        assert ctx["is_admin"] is True
        assert ctx["rate_limit_tier"] == "custom"


@pytest.mark.asyncio
async def test_validate_api_key_returns_admin_context():
    mgr = _manager(api_keys={"sk-admin": "root"}, admin_users=["root"])
    ctx = await mgr.validate_api_key("sk-admin")
    assert ctx is not None
    assert ctx.user_id == "root"
    assert ctx.is_admin is True


def _hash(api_key: str) -> str:
    import hashlib

    return hashlib.sha256(api_key.encode()).hexdigest()
