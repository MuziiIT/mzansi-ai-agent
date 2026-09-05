"""
test_deadline_utils.py — basic smoke tests for deadline parsing/expiry logic.
Run with: python -m pytest test_deadline_utils.py
(or just: python test_deadline_utils.py — it'll run without pytest too)
"""

from datetime import date, timedelta
from deadline_utils import parse_deadline, is_expired

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
NEXT_YEAR = TODAY.replace(year=TODAY.year + 1)


def test_parses_clear_date():
    assert parse_deadline("31 August 2026") is not None


def test_parses_slash_date():
    assert parse_deadline("15/10/2026") is not None


def test_rolling_deadline_has_no_fixed_date():
    assert parse_deadline("Rolling") is None
    assert parse_deadline("N/A") is None
    assert parse_deadline("Ongoing") is None


def test_empty_string_has_no_date():
    assert parse_deadline("") is None
    assert parse_deadline(None) is None


def test_future_date_not_expired():
    future_str = NEXT_YEAR.strftime("%d %B %Y")
    assert is_expired(future_str) is False


def test_past_date_is_expired():
    past_str = YESTERDAY.strftime("%d %B %Y")
    assert is_expired(past_str) is True


def test_rolling_is_never_expired():
    assert is_expired("Rolling") is False
    assert is_expired("N/A") is False


def test_unparseable_text_not_treated_as_expired():
    # We'd rather show an ambiguous bursary than wrongly hide a real one.
    assert is_expired("Contact us for details") is False


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"  PASS: {t.__name__}")
            passed += 1
        except AssertionError:
            print(f"  FAIL: {t.__name__}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")