"""
deadline_utils.py — Parses the free-text 'deadline' field the LLM extracts
(e.g. "31 August 2026", "15/10/2026", "Rolling") into an actual date, so
the pipeline can catch and skip bursaries whose deadline has already
passed, instead of publishing them and letting a student apply too late.
"""

from datetime import datetime, timezone
from dateutil import parser as date_parser

# Deadlines that aren't a fixed date at all — never treat these as expired.
NO_FIXED_DEADLINE_KEYWORDS = (
    "rolling", "ongoing", "until filled", "n/a", "not specified",
    "no deadline", "continuous", "open", "annually", "varies",
)


def parse_deadline(deadline_str: str):
    """
    Returns a datetime.date if a specific closing date could be parsed,
    or None if there's no fixed deadline (rolling/unspecified) or the
    text couldn't be parsed at all. None means "can't tell" — treated
    as NOT expired, since we'd rather show an ambiguous one than
    wrongly hide a real bursary.
    """
    if not deadline_str or not deadline_str.strip():
        return None

    text = deadline_str.strip().lower()
    if any(keyword in text for keyword in NO_FIXED_DEADLINE_KEYWORDS):
        return None

    try:
        # fuzzy=True lets it pull a date out of messier strings like
        # "Applications close 31 August 2026 at 16:00".
        parsed = date_parser.parse(deadline_str, fuzzy=True, dayfirst=True)
        return parsed.date()
    except (ValueError, OverflowError, TypeError):
        return None


def is_expired(deadline_str: str) -> bool:
    """True only when we found a specific date AND it's already passed."""
    parsed = parse_deadline(deadline_str)
    if parsed is None:
        return False
    return parsed < datetime.now(timezone.utc).date()


# The live site stores 'deadline' as a real Firestore Timestamp (confirmed
# from an existing document: "August 31, 2026 at 2:00:00 AM UTC+2"), not
# free text. A string in that field would silently break any query that
# filters on "future deadlines only" — the bursary would still get
# approved and pushed, just never actually show up on the site.
#
# For bursaries with no fixed date (rolling, N/A, unparseable), there's no
# real closing timestamp to store — but we still want them to pass a
# "deadline is in the future" site query rather than vanishing. This
# sentinel is a deliberate placeholder date far enough out that it always
# satisfies that kind of filter, not a real closing date.
NO_FIXED_DEADLINE_SENTINEL = datetime(2099, 12, 31, tzinfo=timezone.utc)


def deadline_to_timestamp(deadline_str: str) -> datetime:
    """
    Converts the extracted deadline text into a timezone-aware datetime,
    suitable for Firestore to store as a native Timestamp (matching the
    live site's existing schema) rather than a string.
    """
    parsed_date = parse_deadline(deadline_str)
    if parsed_date is None:
        return NO_FIXED_DEADLINE_SENTINEL
    return datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=timezone.utc)