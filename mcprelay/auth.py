"""
Authentication and authorization for MCPRelay.
"""

import hashlib
import time
import uuid
from typing import Any, Dict, Optional

import structlog
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

logger = structlog.get_logger()

security = HTTPBearer(auto_error=False)


class AuthContext(BaseModel):
    """Authentication context for requests."""

    user_id: str
    request_id: str
    is_admin: bool = False
    rate_limit_tier: str = "default"
    allowed_mcp_actions: list[str] = ["*"]
    metadata: Dict[str, Any] = {}


class AuthManager:
    """Manages authentication and authorization."""

    def __init__(self, config):
        self.config = config
        self.api_key_cache = {}
        self._build_api_key_cache()

    def _build_api_key_cache(self):
        """Build API key lookup cache."""
        for api_key, user_id in self.config.auth.api_keys.items():
            # Hash API key for security
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            self.api_key_cache[key_hash] = {
                "user_id": user_id,
                "is_admin": user_id.endswith("-admin"),
                "rate_limit_tier": self._get_user_rate_tier(user_id),
            }

    def _get_user_rate_tier(self, user_id: str) -> str:
        """Get rate limit tier for user."""
        if user_id in self.config.rate_limit.per_user_limits:
            return "custom"
        elif user_id.endswith("-admin"):
            return "admin"
        return "default"

    async def validate_api_key(self, api_key: str) -> Optional[AuthContext]:
        """Validate API key and return auth context."""
        try:
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            if key_hash not in self.api_key_cache:
                logger.warning("Invalid API key attempt", key_prefix=api_key[:8])
                return None

            user_info = self.api_key_cache[key_hash]

            return AuthContext(
                user_id=user_info["user_id"],
                request_id=str(uuid.uuid4()),
                is_admin=user_info["is_admin"],
                rate_limit_tier=user_info["rate_limit_tier"],
            )

        except Exception as e:
            logger.error("API key validation error", error=str(e))
            return None

    async def validate_jwt(self, token: str) -> Optional[AuthContext]:
        """Validate JWT token and return auth context."""
        try:
            if not self.config.auth.jwt_secret:
                return None

            payload = jwt.decode(
                token,
                self.config.auth.jwt_secret,
                algorithms=[self.config.auth.jwt_algorithm],
            )

            # Check expiration
            if payload.get("exp", 0) < time.time():
                logger.warning("Expired JWT token")
                return None

            user_id = payload.get("sub")
            if not user_id:
                logger.warning("JWT missing subject")
                return None

            return AuthContext(
                user_id=user_id,
                request_id=str(uuid.uuid4()),
                is_admin=payload.get("admin", False),
                rate_limit_tier=payload.get("tier", "default"),
                allowed_mcp_actions=payload.get("mcp_actions", ["*"]),
            )

        except JWTError as e:
            logger.warning("JWT validation failed", error=str(e))
            return None
        except Exception as e:
            logger.error("JWT validation error", error=str(e))
            return None


# Global auth manager - will be initialized by server
auth_manager: Optional[AuthManager] = None


def init_auth_manager(config):
    """Initialize global auth manager."""
    global auth_manager
    auth_manager = AuthManager(config)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> AuthContext:
    """Get current authenticated user."""

    if not auth_manager:
        raise HTTPException(status_code=500, detail="Auth not initialized")

    if not auth_manager.config.auth.enabled:
        # Auth disabled - return default context
        return AuthContext(user_id="anonymous", request_id=str(uuid.uuid4()))

    # Try different auth methods
    auth_context = None

    # 1. Check Authorization header (Bearer token)
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials

        # Try JWT first
        if auth_manager.config.auth.method in ["jwt", "oauth"]:
            auth_context = await auth_manager.validate_jwt(token)

        # Fall back to API key
        if not auth_context and auth_manager.config.auth.method == "api_key":
            auth_context = await auth_manager.validate_api_key(token)

    # 2. Check X-API-Key header
    if not auth_context:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            auth_context = await auth_manager.validate_api_key(api_key)

    # 3. Check query parameter (less secure, for development)
    if not auth_context and auth_manager.config.debug_mode:
        api_key = request.query_params.get("api_key")
        if api_key:
            auth_context = await auth_manager.validate_api_key(api_key)

    if not auth_context:
        logger.warning(
            "Authentication failed",
            ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("User-Agent", ""),
            path=request.url.path,
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Log successful authentication
    logger.info(
        "Request authenticated",
        user=auth_context.user_id,
        request_id=auth_context.request_id,
        ip=request.client.host if request.client else "unknown",
    )

    return auth_context


async def require_admin(
    auth_context: AuthContext = Depends(get_current_user),
) -> AuthContext:
    """Require admin privileges."""
    if not auth_context.is_admin:
        logger.warning("Admin access denied", user=auth_context.user_id)
        raise HTTPException(status_code=403, detail="Admin access required")
    return auth_context
