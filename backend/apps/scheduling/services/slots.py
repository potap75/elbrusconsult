"""Slot generation for the booking calendar.

Pure functions: given the current availability configuration and any existing
bookings, return the list of bookable slot start times for an appointment type.

All times in / out are UTC ``datetime`` objects. Weekly ``AvailabilityRule``
rows are interpreted in ``settings.SCHEDULING_TIMEZONE`` (e.g. business hours
in the company's local time), then projected to UTC before being intersected
with blackouts and existing bookings.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone as djtz

from ..models import (
    AppointmentType,
    AvailabilityException,
    AvailabilityRule,
    Booking,
)


@dataclass(frozen=True)
class Interval:
    """A closed/open ``[start, end)`` interval in UTC."""

    start: datetime
    end: datetime

    def overlaps(self, other: "Interval") -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: "Interval") -> bool:
        return self.start <= other.start and other.end <= self.end


def _company_tz() -> ZoneInfo:
    return ZoneInfo(getattr(settings, "SCHEDULING_TIMEZONE", "UTC"))


def _windows_for_date(rules: Iterable[AvailabilityRule], day: date) -> list[Interval]:
    """Project all rules matching ``day``'s weekday onto absolute UTC intervals."""
    tz = _company_tz()
    out: list[Interval] = []
    for rule in rules:
        if rule.weekday != day.weekday() or not rule.is_active:
            continue
        if rule.start_time >= rule.end_time:
            continue
        start_local = datetime.combine(day, rule.start_time, tzinfo=tz)
        end_local = datetime.combine(day, rule.end_time, tzinfo=tz)
        out.append(
            Interval(start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc))
        )
    return out


def _subtract(window: Interval, blocks: list[Interval]) -> list[Interval]:
    """Return the parts of ``window`` left after removing every blocking interval."""
    remaining = [window]
    for block in blocks:
        next_remaining: list[Interval] = []
        for piece in remaining:
            if not piece.overlaps(block):
                next_remaining.append(piece)
                continue
            if block.start > piece.start:
                next_remaining.append(Interval(piece.start, min(piece.end, block.start)))
            if block.end < piece.end:
                next_remaining.append(Interval(max(piece.start, block.end), piece.end))
        remaining = [i for i in next_remaining if i.end > i.start]
    return remaining


def _slice(window: Interval, *, slot_length: timedelta, step: timedelta) -> list[datetime]:
    """Yield slot start times that fit fully inside ``window``."""
    starts: list[datetime] = []
    cursor = window.start
    while cursor + slot_length <= window.end:
        starts.append(cursor)
        cursor = cursor + step
    return starts


def _round_up(dt: datetime, step: timedelta) -> datetime:
    """Round ``dt`` up to the next multiple of ``step`` after the UTC epoch."""
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = dt - epoch
    step_seconds = int(step.total_seconds())
    remainder = int(delta.total_seconds()) % step_seconds
    if remainder == 0 and dt.microsecond == 0:
        return dt
    return dt + timedelta(seconds=step_seconds - remainder) - timedelta(microseconds=dt.microsecond)


def generate_slots(
    appointment_type: AppointmentType,
    date_from: date,
    date_to: date,
    *,
    now: datetime | None = None,
    ignore_booking_ids: Iterable[int] = (),
) -> list[datetime]:
    """Return UTC datetimes that are valid start times for ``appointment_type``.

    ``date_from`` and ``date_to`` are *inclusive* calendar days interpreted in
    the company timezone (i.e. "show me available slots from Mon to Sun in
    the customer's view"). Slots that begin earlier than
    ``SCHEDULING_MIN_LEAD_MINUTES`` from now, or later than
    ``SCHEDULING_MAX_LEAD_DAYS`` from now, are filtered out.
    """
    if not appointment_type.is_active:
        return []
    if date_from > date_to:
        return []

    now = now or djtz.now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    duration = timedelta(minutes=appointment_type.duration_minutes)
    buffer_after = timedelta(minutes=appointment_type.buffer_after_minutes)
    step = timedelta(minutes=getattr(settings, "SCHEDULING_SLOT_GRANULARITY_MINUTES", 15))
    min_lead = timedelta(minutes=getattr(settings, "SCHEDULING_MIN_LEAD_MINUTES", 0))
    max_lead = timedelta(days=getattr(settings, "SCHEDULING_MAX_LEAD_DAYS", 365))

    earliest = now + min_lead
    latest = now + max_lead

    tz = _company_tz()
    range_start_utc = datetime.combine(date_from, time.min, tzinfo=tz).astimezone(timezone.utc)
    range_end_utc = datetime.combine(
        date_to + timedelta(days=1), time.min, tzinfo=tz
    ).astimezone(timezone.utc)

    rules = list(AvailabilityRule.objects.filter(is_active=True))
    exceptions = list(
        AvailabilityException.objects.filter(
            start_at__lt=range_end_utc,
            end_at__gt=range_start_utc,
        )
    )
    bookings_qs = Booking.objects.filter(
        status=Booking.Status.CONFIRMED,
        start_at__lt=range_end_utc,
        end_at__gt=range_start_utc,
    ).only("start_at", "end_at")
    ignored = list(ignore_booking_ids)
    if ignored:
        bookings_qs = bookings_qs.exclude(id__in=ignored)
    bookings = list(bookings_qs)

    blocks: list[Interval] = []
    for ex in exceptions:
        blocks.append(
            Interval(
                _ensure_utc(ex.start_at),
                _ensure_utc(ex.end_at),
            )
        )
    for b in bookings:
        blocks.append(
            Interval(
                _ensure_utc(b.start_at),
                _ensure_utc(b.end_at) + buffer_after,
            )
        )

    results: list[datetime] = []
    current = date_from
    one_day = timedelta(days=1)
    while current <= date_to:
        for window in _windows_for_date(rules, current):
            for piece in _subtract(window, blocks):
                aligned_start = max(
                    _round_up(piece.start, step),
                    _round_up(earliest, step),
                )
                effective = Interval(aligned_start, min(piece.end, latest))
                if effective.end <= effective.start:
                    continue
                results.extend(_slice(effective, slot_length=duration, step=step))
        current = current + one_day

    seen: set[datetime] = set()
    deduped: list[datetime] = []
    for slot in results:
        if slot not in seen:
            deduped.append(slot)
            seen.add(slot)
    deduped.sort()
    return deduped


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def slot_is_available(
    appointment_type: AppointmentType,
    start_at: datetime,
    *,
    now: datetime | None = None,
    exclude_booking_id: int | None = None,
) -> bool:
    """Return True iff ``start_at`` is currently a valid slot start.

    Used to validate the customer-supplied ``start_at`` server-side before we
    write a Booking row. If ``exclude_booking_id`` is given, that booking is
    ignored (useful for reschedules where we're about to cancel the original).
    """
    start_at = _ensure_utc(start_at)
    tz = _company_tz()
    local_day = start_at.astimezone(tz).date()
    ignore = (exclude_booking_id,) if exclude_booking_id is not None else ()
    candidates = generate_slots(
        appointment_type,
        local_day,
        local_day,
        now=now,
        ignore_booking_ids=ignore,
    )
    return start_at in candidates
