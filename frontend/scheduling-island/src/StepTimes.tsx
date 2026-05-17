import { formatLongDate, formatTime } from "./dateUtils";

type Props = {
  dayKey: string;
  slots: Date[];
  timezone: string;
  selectedSlot: Date | null;
  onPickSlot: (slot: Date) => void;
  onChangeTimezone: (tz: string) => void;
};

const COMMON_TIMEZONES = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Toronto",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Dubai",
  "Asia/Kolkata",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Australia/Sydney",
  "UTC",
];

export function StepTimes({
  dayKey,
  slots,
  timezone,
  selectedSlot,
  onPickSlot,
  onChangeTimezone,
}: Props) {
  const displayDate = slots[0]
    ? formatLongDate(slots[0], timezone)
    : new Date(dayKey).toDateString();

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-900">Pick a time</h2>
      <p className="mt-1 text-sm text-slate-600">{displayDate}</p>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor="sched-tz" className="text-slate-600">Times in:</label>
        <select
          id="sched-tz"
          value={timezone}
          onChange={(e) => onChangeTimezone(e.target.value)}
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-slate-900 focus:outline-none focus:ring-2 focus:ring-summit-500 focus:border-summit-500"
        >
          {!COMMON_TIMEZONES.includes(timezone) && (
            <option value={timezone}>{timezone}</option>
          )}
          {COMMON_TIMEZONES.map((tz) => (
            <option key={tz} value={tz}>{tz}</option>
          ))}
        </select>
      </div>

      {slots.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">
          No times left for this day. Pick another date.
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2">
          {slots.map((slot) => {
            const isSelected =
              selectedSlot !== null && slot.getTime() === selectedSlot.getTime();
            return (
              <button
                key={slot.toISOString()}
                type="button"
                onClick={() => onPickSlot(slot)}
                className={`rounded-md border px-3 py-2 text-sm font-medium ${
                  isSelected
                    ? "border-summit-600 bg-summit-600 text-white"
                    : "border-slate-200 bg-white text-slate-700 hover:border-summit-400 hover:text-summit-700"
                }`}
              >
                {formatTime(slot, timezone)}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
