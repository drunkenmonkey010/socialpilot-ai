import random
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    """
    Configuration for scheduled publication retries.

    Retry delays use exponential backoff with bounded jitter.

    Example with the default policy:

        Attempt 1 -> around 30 seconds
        Attempt 2 -> around 60 seconds
        Attempt 3 -> around 120 seconds
        Attempt 4 -> around 240 seconds

    Jitter prevents many workers from retrying at exactly the
    same moment.
    """

    max_attempts: int = 5
    initial_backoff_seconds: int = 30
    max_backoff_seconds: int = 15 * 60
    jitter_ratio: float = 0.20

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(
                "max_attempts must be at least 1."
            )

        if self.initial_backoff_seconds < 1:
            raise ValueError(
                "initial_backoff_seconds must be at least 1."
            )

        if self.max_backoff_seconds < 1:
            raise ValueError(
                "max_backoff_seconds must be at least 1."
            )

        if (
            self.max_backoff_seconds
            < self.initial_backoff_seconds
        ):
            raise ValueError(
                "max_backoff_seconds cannot be smaller than "
                "initial_backoff_seconds."
            )

        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError(
                "jitter_ratio must be between 0 and 1."
            )

    def calculate_backoff(
        self,
        attempt: int,
    ) -> int:
        """
        Calculate exponential backoff without jitter.

        This method is deterministic and useful for testing
        the exponential backoff calculation independently.
        """

        if attempt < 1:
            raise ValueError(
                "attempt must be at least 1."
            )

        delay = (
            self.initial_backoff_seconds
            * (2 ** (attempt - 1))
        )

        return min(
            delay,
            self.max_backoff_seconds,
        )

    def calculate_retry_delay(
        self,
        attempt: int,
    ) -> int:
        """
        Calculate the final retry delay including jitter.

        Jitter is applied around the calculated exponential
        backoff value.

        Example with jitter_ratio=0.20:

            30 seconds -> 24 to 36 seconds
            60 seconds -> 48 to 72 seconds
        """

        base_delay = self.calculate_backoff(
            attempt,
        )

        if self.jitter_ratio == 0:
            return base_delay

        lower_bound = (
            base_delay
            * (1 - self.jitter_ratio)
        )

        upper_bound = (
            base_delay
            * (1 + self.jitter_ratio)
        )

        jittered_delay = random.uniform(
            lower_bound,
            upper_bound,
        )

        return min(
            int(round(jittered_delay)),
            self.max_backoff_seconds,
        )


retry_policy = RetryPolicy()