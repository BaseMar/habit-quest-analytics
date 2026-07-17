from __future__ import annotations

from datetime import date, datetime, time, timedelta


def end_at_for_duration(planned_date: date, start_time: time, duration_minutes: int) -> datetime:
    """Return the end datetime for a same-day scheduling input."""
    return datetime.combine(planned_date, start_time) + timedelta(minutes=int(duration_minutes))


def duration_crosses_midnight(planned_date: date, start_time: time, duration_minutes: int) -> bool:
    """Return whether a scheduling duration ends after the selected day."""
    return end_at_for_duration(planned_date, start_time, duration_minutes).date() != planned_date
