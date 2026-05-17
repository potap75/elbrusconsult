import { useEffect, useMemo, useState } from "react";
import {
  isInMonth,
  localDayKey,
  monthGridDays,
  monthLabel,
  nextMonth,
  prevMonth,
  todayKey,
  ymd,
} from "./dateUtils";

type Props = {
  timezone: string;
  selectedDayKey: string | null;
  loading: boolean;
  slotsByDay: Record<string, Date[]>;
  monthAnchor: Date;
  onMonthChange: (anchor: Date) => void;
  onPickDay: (dayKey: string) => void;
};

export function StepCalendar({
  timezone,
  selectedDayKey,
  loading,
  slotsByDay,
  monthAnchor,
  onMonthChange,
  onPickDay,
}: Props) {
  const days = useMemo(() => monthGridDays(monthAnchor, timezone), [monthAnchor, timezone]);
  const today = useMemo(() => todayKey(timezone), [timezone]);
  const [keyboardFocus, setKeyboardFocus] = useState<string | null>(null);

  useEffect(() => {
    setKeyboardFocus(null);
  }, [monthAnchor]);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Pick a date</h2>
          <p className="mt-1 text-sm text-slate-600">
            Dates with availability are highlighted. Times shown in{" "}
            <span className="font-medium">{timezone}</span>.
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onMonthChange(prevMonth(monthAnchor))}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm hover:bg-slate-50"
            aria-label="Previous month"
          >
            &larr;
          </button>
          <span className="px-3 text-sm font-medium tabular-nums">
            {monthLabel(monthAnchor, timezone)}
          </span>
          <button
            type="button"
            onClick={() => onMonthChange(nextMonth(monthAnchor))}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm hover:bg-slate-50"
            aria-label="Next month"
          >
            &rarr;
          </button>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-7 gap-1 text-center text-xs font-medium text-slate-500">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
          <div key={d} className="py-1">{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {days.map((day) => {
          const key = localDayKey(day, timezone);
          const inMonth = isInMonth(day, monthAnchor, timezone);
          const slots = slotsByDay[key] ?? [];
          const hasSlots = slots.length > 0;
          const isPast = key < today;
          const isSelected = selectedDayKey === key;
          const disabled = !inMonth || isPast || !hasSlots;
          return (
            <button
              key={`${ymd(day)}-${key}`}
              type="button"
              disabled={disabled}
              onClick={() => onPickDay(key)}
              onFocus={() => setKeyboardFocus(key)}
              className={`aspect-square rounded-md text-sm font-medium relative ${
                disabled
                  ? "text-slate-300 cursor-not-allowed"
                  : isSelected
                    ? "bg-summit-600 text-white"
                    : "bg-white border border-slate-200 text-slate-700 hover:border-summit-400 hover:text-summit-700"
              } ${keyboardFocus === key && !disabled ? "ring-2 ring-summit-300" : ""}`}
              aria-label={key + (hasSlots ? `, ${slots.length} times available` : ", no availability")}
            >
              <span>{day.getDate()}</span>
              {hasSlots && inMonth && !isSelected && !isPast && (
                <span className="absolute bottom-1 left-1/2 -translate-x-1/2 h-1 w-1 rounded-full bg-summit-500" aria-hidden="true"></span>
              )}
            </button>
          );
        })}
      </div>

      {loading && (
        <p className="mt-4 text-sm text-slate-500">Loading availability...</p>
      )}
    </div>
  );
}
