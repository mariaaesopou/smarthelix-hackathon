EXIT_OK = 0
EXIT_RETRYABLE = 75  # transient: BullMQ applies attempts + backoff
EXIT_PERMANENT = 65  # retrying cannot help: BullMQ fails the job at once


class RetryableError(Exception):
    """Raise when trying again later could succeed (DB briefly down, source 503).

    `retry_after_s` carries a source's own Retry-After hint (HTTP 429/503). The CLI
    reports it to the launcher, and the queue waits at least that long.
    """

    def __init__(self, message: str = "", retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class PermanentError(Exception):
    """Raise when the same input will always fail (invalid payload, missing source)."""
