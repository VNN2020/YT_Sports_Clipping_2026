
"""
Rate limiter for YouTube API and HTTP requests.
"""

import os
import time
import random
import logging
import threading
from collections import defaultdict
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket rate limiter for API calls."""

    def __init__(self, rate: float, burst: int):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.rate
        self.tokens = min(self.burst, self.tokens + new_tokens)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_and_consume(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.consume(tokens):
                return True
            time.sleep(0.1)
        return False


class RateLimiter:
    """Centralized rate limiter for YouTube API and HTTP requests."""

    YOUTUBE_QUOTA = {
        "search": 100,
        "videos.list": 1,
        "videos.insert": 1600,
        "channels.list": 1,
        "playlistItems.insert": 50,
        "commentThreads.insert": 50,
    }

    DAILY_QUOTA_LIMIT = 10_000
    MAX_UPLOADS_PER_DAY = 2  # Views jail prevention — cap uploads/channel/day

    def __init__(self, quota_file: Optional[str] = None):
        self.quota_file = quota_file
        self.quota_used = 0
        self.quota_reset_time = time.time() + 86400
        self.uploads_today = 0
        self.uploads_day_date = ""
        self.domain_buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(rate=2.0, burst=5)
        )
        self._lock = threading.Lock()
        self._load_quota()
        self._load_upload_count()

    def _load_quota(self):
        if self.quota_file and os.path.exists(self.quota_file):
            try:
                with open(self.quota_file, "r") as f:
                    data = f.read().strip().split(",")
                    if len(data) == 2:
                        self.quota_used = int(data[0])
                        self.quota_reset_time = float(data[1])
            except (ValueError, OSError):
                pass

    def _save_quota(self):
        if self.quota_file:
            try:
                os.makedirs(os.path.dirname(self.quota_file), exist_ok=True)
                with open(self.quota_file, "w") as f:
                    f.write(f"{self.quota_used},{self.quota_reset_time}")
            except OSError:
                pass

    def _reset_if_needed(self):
        now = time.time()
        if now >= self.quota_reset_time:
            self.quota_used = 0
            self.quota_reset_time = now + 86400
            self._save_quota()

    def _load_upload_count(self):
        upload_count_file = str(self.quota_file).replace(".json", "_uploads.txt") if self.quota_file else None
        if upload_count_file and os.path.exists(upload_count_file):
            try:
                with open(upload_count_file, "r") as f:
                    data = f.read().strip().split(",")
                    if len(data) == 2:
                        self.uploads_today = int(data[0])
                        self.uploads_day_date = data[1]
            except (ValueError, OSError):
                pass

    def _save_upload_count(self):
        upload_count_file = str(self.quota_file).replace(".json", "_uploads.txt") if self.quota_file else None
        if upload_count_file:
            try:
                os.makedirs(os.path.dirname(upload_count_file), exist_ok=True)
                with open(upload_count_file, "w") as f:
                    f.write(f"{self.uploads_today},{self.uploads_day_date}")
            except OSError:
                pass

    def _reset_uploads_if_needed(self):
        today = time.strftime("%Y-%m-%d")
        if self.uploads_day_date != today:
            self.uploads_today = 0
            self.uploads_day_date = today
            self._save_upload_count()

    def check_upload_cap(self) -> bool:
        """Returns True if under the daily upload cap (views jail prevention)."""
        with self._lock:
            self._reset_uploads_if_needed()
            return self.uploads_today < self.MAX_UPLOADS_PER_DAY

    def record_upload(self):
        """Record an upload for the views jail counter."""
        with self._lock:
            self._reset_uploads_if_needed()
            self.uploads_today += 1
            self._save_upload_count()

    def get_quota_remaining(self) -> int:
        with self._lock:
            self._reset_if_needed()
            return max(0, self.DAILY_QUOTA_LIMIT - self.quota_used)

    def check_quota(self, action: str, units: Optional[int] = None) -> bool:
        with self._lock:
            self._reset_if_needed()
            cost = units or self.YOUTUBE_QUOTA.get(action, 1)
            return (self.quota_used + cost) <= self.DAILY_QUOTA_LIMIT

    def deduct_quota(self, action: str, units: Optional[int] = None) -> bool:
        with self._lock:
            self._reset_if_needed()
            cost = units or self.YOUTUBE_QUOTA.get(action, 1)
            if (self.quota_used + cost) <= self.DAILY_QUOTA_LIMIT:
                self.quota_used += cost
                self._save_quota()
                return True
            return False

    def download_throttle(self, domain: str = "youtube"):
        return DomainThrottle(self, domain)

    def http_throttle(self, domain: str = "youtube"):
        return DomainThrottle(self, domain)

    def retry_with_backoff(
        self,
        fn: Callable,
        max_retries: int = 5,
        base_delay: float = 10.0,
        cap: float = 300.0,
        *args,
        **kwargs,
    ) -> Any:
        for attempt in range(max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries:
                    raise
                delay = min(cap, base_delay * (2 ** attempt))
                jitter = random.uniform(0, delay * 0.1)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {delay + jitter:.1f}s..."
                )
                time.sleep(delay + jitter)


class DomainThrottle:
    def __init__(self, rate_limiter: RateLimiter, domain: str):
        self.rate_limiter = rate_limiter
        self.domain = domain
        self.bucket: Optional[TokenBucket] = None

    def __enter__(self):
        self.bucket = self.rate_limiter.domain_buckets[self.domain]
        self.bucket.wait_and_consume(1)
        return self

    def __exit__(self, *args):
        pass


def jitter(delay: float) -> float:
    return delay * random.uniform(0.9, 1.1)


rate_limiter = RateLimiter()
