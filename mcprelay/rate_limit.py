"""
Rate limiting for MCPRelay.
"""

import asyncio
import time
from typing import Dict, Optional

import structlog
from fastapi import Depends, HTTPException, Request

from .auth import AuthContext

logger = structlog.get_logger()


class TokenBucket:
    """Token bucket rate limiter."""

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens: float = float(capacity)
        self.refill_rate = refill_rate
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from bucket."""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_refill

            # Refill tokens
            new_tokens = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_refill = now

            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False


class RateLimiter:
    """Per-user rate limiter."""

    def __init__(self, config):
        self.config = config
        self.buckets: Dict[str, TokenBucket] = {}
        self.cleanup_task = None

        if config.rate_limit.enabled:
            self.cleanup_task = asyncio.create_task(self._cleanup_buckets())

    def _get_user_limit(self, auth_context: AuthContext) -> int:
        """Get rate limit for user."""
        user_id = auth_context.user_id

        # Check per-user limits first
        if user_id in self.config.rate_limit.per_user_limits:
            return int(self.config.rate_limit.per_user_limits[user_id])

        # Admin users get higher limits
        if auth_context.is_admin:
            return int(self.config.rate_limit.default_requests_per_minute * 3)

        # Default limit
        return int(self.config.rate_limit.default_requests_per_minute)

    async def check_rate_limit(self, auth_context: AuthContext) -> bool:
        """Check if request is within rate limit."""
        if not self.config.rate_limit.enabled:
            return True

        user_id = auth_context.user_id

        # Get or create bucket for user
        if user_id not in self.buckets:
            requests_per_minute = self._get_user_limit(auth_context)
            burst_size = self.config.rate_limit.burst_size

            # Convert per-minute to per-second rate
            refill_rate = requests_per_minute / 60.0

            self.buckets[user_id] = TokenBucket(burst_size, refill_rate)

        bucket = self.buckets[user_id]
        allowed = await bucket.consume(1)

        if not allowed:
            logger.warning(
                "Rate limit exceeded",
                user=user_id,
                limit=self._get_user_limit(auth_context),
            )

        return allowed

    async def _cleanup_buckets(self):
        """Periodically clean up unused buckets."""
        while True:
            await asyncio.sleep(300)  # Clean up every 5 minutes

            current_time = time.time()
            expired_users = []

            for user_id, bucket in self.buckets.items():
                # Remove buckets unused for 10 minutes
                if current_time - bucket.last_refill > 600:
                    expired_users.append(user_id)

            for user_id in expired_users:
                del self.buckets[user_id]

            if expired_users:
                logger.debug(
                    f"Cleaned up {len(expired_users)} expired rate limit buckets"
                )

    def stop(self):
        """Stop the rate limiter."""
        if self.cleanup_task:
            self.cleanup_task.cancel()


# Global rate limiter - will be initialized by server
rate_limiter: Optional[RateLimiter] = None


def init_rate_limiter(config):
    """Initialize global rate limiter."""
    global rate_limiter
    rate_limiter = RateLimiter(config)


async def rate_limit_check(
    request: Request, auth_context: AuthContext = Depends()
) -> None:
    """Dependency to check rate limits."""

    if not rate_limiter:
        return  # Rate limiting not initialized

    allowed = await rate_limiter.check_rate_limit(auth_context)

    if not allowed:
        # Add rate limit headers
        user_limit = rate_limiter._get_user_limit(auth_context)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(user_limit),
                "X-RateLimit-Remaining": "0",
                "Retry-After": "60",
            },
        )
