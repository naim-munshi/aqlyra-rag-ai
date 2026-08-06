from datetime import UTC, datetime


def utc_now_naive() -> datetime:
    """
    Return the current UTC time without timezone information.

    Existing database columns store naive UTC datetimes, so this
    keeps the current schema behavior while avoiding utcnow().
    """

    return datetime.now(UTC).replace(
        tzinfo=None
    )
