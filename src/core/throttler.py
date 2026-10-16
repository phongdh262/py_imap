import time
from typing import Optional
from rich.console import Console

from src.telemetry.logger import setup_logging
from src.telemetry.metrics import MESSAGES_FAILED_TOTAL

console = Console()
logger = setup_logging()

THROTTLING_PATTERNS = [
    "too many simultaneous connections",
    "maximum bandwidth exceeded",
    "exceededquota",
    "throttled",
    "user is over quota",
    "server busy",
    "rate limit",
    "temporary lookup failure",
    "connection reset by peer",
    "try again later",
    "socket error",
]


class ProviderThrottler:
    """
    Intelligent Rate-Limiter and Anti-Ban Engine:
    - Injects controlled delay between IMAP batch requests
    - Detects provider-specific throttling responses (Gmail, Outlook, Yandex)
    - Automatically executes Exponential Backoff & Reconnects
    """

    def __init__(
        self,
        batch_delay_seconds: float = 0.05,
        max_retries: int = 3,
        base_backoff_seconds: float = 5.0,
    ):
        self.batch_delay = batch_delay_seconds
        self.max_retries = max_retries
        self.base_backoff = base_backoff_seconds

    def throttle_batch(self):
        """Applies configured sleep between batches to protect against provider rate limits."""
        if self.batch_delay > 0:
            time.sleep(self.batch_delay)

    @staticmethod
    def is_throttled_error(error_message: str) -> bool:
        """Checks if an error response corresponds to rate-limiting / throttling."""
        lower_err = error_message.lower()
        return any(pattern in lower_err for pattern in THROTTLING_PATTERNS)

    def wait_backoff(self, attempt: int, account: str, host: str, error_detail: str):
        """Calculates and sleeps for exponential backoff duration."""
        backoff_sec = self.base_backoff * (2 ** (attempt - 1))
        logger.warning(
            "Provider throttling detected, applying exponential backoff",
            account=account,
            host=host,
            attempt=attempt,
            sleep_seconds=backoff_sec,
            error=error_detail,
        )
        console.print(
            f"[bold yellow]⚠️ Throttling phát hiện từ {host}! Tự động dừng nghỉ {backoff_sec:.1f}s trước khi thử lại (Lần {attempt}/{self.max_retries})...[/bold yellow]"
        )
        time.sleep(backoff_sec)
