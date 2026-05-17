import type { AppointmentType, BookingFormState, Service } from "./types";
import { formatLongDate, formatTime } from "./dateUtils";

type Props = {
  appointmentType: AppointmentType;
  slot: Date;
  timezone: string;
  form: BookingFormState;
  services: Service[];
  fieldErrors: Record<string, string[]>;
  submitting: boolean;
  errorMessage: string | null;
  onUpdate: (key: keyof BookingFormState, value: string) => void;
  onSubmit: () => void;
};

const inputClass =
  "mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-summit-500 focus:border-summit-500";

export function StepDetails({
  appointmentType,
  slot,
  timezone,
  form,
  services,
  fieldErrors,
  submitting,
  errorMessage,
  onUpdate,
  onSubmit,
}: Props) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="grid grid-cols-1 md:grid-cols-2 gap-5"
      noValidate
    >
      <div className="md:col-span-2 rounded-md border border-summit-200 bg-summit-50 px-4 py-3 text-sm text-summit-900">
        <strong>{appointmentType.name}</strong> &middot;{" "}
        {appointmentType.duration_minutes} min &middot;{" "}
        {formatLongDate(slot, timezone)} at {formatTime(slot, timezone)} ({timezone})
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="sched-name">
          Name <span className="text-rose-600">*</span>
        </label>
        <input
          id="sched-name"
          className={inputClass}
          type="text"
          required
          autoComplete="name"
          value={form.name}
          onChange={(e) => onUpdate("name", e.target.value)}
        />
        {fieldErrors.name?.[0] && (
          <p className="mt-1 text-sm text-rose-600">{fieldErrors.name[0]}</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="sched-email">
          Email <span className="text-rose-600">*</span>
        </label>
        <input
          id="sched-email"
          className={inputClass}
          type="email"
          required
          autoComplete="email"
          value={form.email}
          onChange={(e) => onUpdate("email", e.target.value)}
        />
        {fieldErrors.email?.[0] && (
          <p className="mt-1 text-sm text-rose-600">{fieldErrors.email[0]}</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="sched-company">
          Company
        </label>
        <input
          id="sched-company"
          className={inputClass}
          type="text"
          autoComplete="organization"
          value={form.company}
          onChange={(e) => onUpdate("company", e.target.value)}
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="sched-phone">
          Phone
        </label>
        <input
          id="sched-phone"
          className={inputClass}
          type="tel"
          autoComplete="tel"
          value={form.phone}
          onChange={(e) => onUpdate("phone", e.target.value)}
        />
      </div>

      <div className="md:col-span-2">
        <label className="block text-sm font-medium text-slate-700" htmlFor="sched-service">
          Topic / service area
        </label>
        <select
          id="sched-service"
          className={inputClass}
          value={form.service}
          onChange={(e) => onUpdate("service", e.target.value)}
        >
          <option value="">Choose one (optional)...</option>
          {services.map((s) => (
            <option key={s.id} value={String(s.id)}>{s.name}</option>
          ))}
        </select>
      </div>

      <div className="md:col-span-2">
        <label className="block text-sm font-medium text-slate-700" htmlFor="sched-notes">
          Notes
        </label>
        <textarea
          id="sched-notes"
          className={inputClass}
          rows={4}
          placeholder="Anything we should know? Scope, urgency, environments..."
          value={form.notes}
          onChange={(e) => onUpdate("notes", e.target.value)}
        />
      </div>

      {errorMessage && (
        <div className="md:col-span-2 rounded-md border border-rose-300 bg-rose-50 px-4 py-3 text-rose-800">
          {errorMessage}
        </div>
      )}

      <div className="md:col-span-2 flex items-center justify-end">
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex items-center rounded-md bg-summit-600 px-5 py-3 text-white font-semibold hover:bg-summit-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Booking..." : "Confirm booking"}
        </button>
      </div>
    </form>
  );
}
