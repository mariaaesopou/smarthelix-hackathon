EXIT_OK = 0
EXIT_RETRYABLE = 75  # transient: BullMQ applies attempts + backoff
EXIT_PERMANENT = 65  # retrying cannot help: BullMQ fails the job at once


class RetryableError(Exception):
    """Raise when trying again later could succeed (DB briefly down, source 503)."""


class PermanentError(Exception):
    """Raise when the same input will always fail (invalid payload, missing source)."""
