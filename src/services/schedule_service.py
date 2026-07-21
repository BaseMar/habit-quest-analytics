from calendar import monthrange
from datetime import date


def build_month_days(year: int, month: int) -> list[date]:
    """Return every date in a validated calendar month."""
    if year < 1:
        raise ValueError("year must be 1 or greater.")
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12.")

    return [date(year, month, day) for day in range(1, monthrange(year, month)[1] + 1)]
