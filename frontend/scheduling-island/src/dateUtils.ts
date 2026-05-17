import { addDays, addMonths, endOfMonth, format, startOfMonth } from "date-fns";
import { formatInTimeZone, toZonedTime } from "date-fns-tz";

export function detectTimezone(fallback: string): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || fallback;
  } catch {
    return fallback;
  }
}

export function ymd(date: Date): string {
  return format(date, "yyyy-MM-dd");
}

export function monthGridDays(monthAnchor: Date, timezone: string): Date[] {
  const localAnchor = toZonedTime(monthAnchor, timezone);
  const first = startOfMonth(localAnchor);
  const last = endOfMonth(localAnchor);
  const start = addDays(first, -first.getDay());
  const days: Date[] = [];
  let cursor = start;
  while (cursor <= last || days.length % 7 !== 0) {
    days.push(cursor);
    cursor = addDays(cursor, 1);
    if (days.length > 42) break;
  }
  return days;
}

export function isSameLocalDay(a: Date, b: Date, timezone: string): boolean {
  return (
    formatInTimeZone(a, timezone, "yyyy-MM-dd") ===
    formatInTimeZone(b, timezone, "yyyy-MM-dd")
  );
}

export function localDayKey(d: Date, timezone: string): string {
  return formatInTimeZone(d, timezone, "yyyy-MM-dd");
}

export function formatTime(d: Date, timezone: string): string {
  return formatInTimeZone(d, timezone, "HH:mm");
}

export function formatLongDate(d: Date, timezone: string): string {
  return formatInTimeZone(d, timezone, "EEEE, MMMM d, yyyy");
}

export function nextMonth(d: Date): Date {
  return addMonths(d, 1);
}

export function prevMonth(d: Date): Date {
  return addMonths(d, -1);
}

export function monthLabel(d: Date, timezone: string): string {
  return formatInTimeZone(d, timezone, "MMMM yyyy");
}

export function isInMonth(day: Date, monthAnchor: Date, timezone: string): boolean {
  return (
    formatInTimeZone(day, timezone, "yyyy-MM") ===
    formatInTimeZone(monthAnchor, timezone, "yyyy-MM")
  );
}

export function todayKey(timezone: string): string {
  return formatInTimeZone(new Date(), timezone, "yyyy-MM-dd");
}
