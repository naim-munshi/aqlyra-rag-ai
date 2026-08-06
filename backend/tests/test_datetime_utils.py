from datetime import UTC, datetime

from app.core.datetime_utils import (
    utc_now_naive,
)


def test_utc_now_naive_returns_current_utc(
) -> None:
    before = datetime.now(
        UTC
    ).replace(
        tzinfo=None
    )

    value = utc_now_naive()

    after = datetime.now(
        UTC
    ).replace(
        tzinfo=None
    )

    assert value.tzinfo is None
    assert before <= value <= after
