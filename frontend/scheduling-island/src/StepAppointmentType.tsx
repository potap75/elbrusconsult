import type { AppointmentType } from "./types";

type Props = {
  appointmentTypes: AppointmentType[];
  selected: AppointmentType | null;
  onPick: (t: AppointmentType) => void;
};

export function StepAppointmentType({ appointmentTypes, selected, onPick }: Props) {
  if (appointmentTypes.length === 0) {
    return (
      <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        No appointment types are currently bookable. Please use the contact
        form and we'll schedule with you directly.
      </div>
    );
  }
  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-900">What would you like to book?</h2>
      <p className="mt-1 text-sm text-slate-600">Pick a meeting type to get started.</p>
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        {appointmentTypes.map((t) => {
          const isSelected = selected?.slug === t.slug;
          return (
            <button
              key={t.slug}
              type="button"
              onClick={() => onPick(t)}
              className={`text-left rounded-lg border p-4 transition focus:outline-none focus:ring-2 focus:ring-summit-500 ${
                isSelected
                  ? "border-summit-600 bg-summit-50 ring-2 ring-summit-200"
                  : "border-slate-200 bg-white hover:border-summit-400"
              }`}
            >
              <div className="flex items-baseline justify-between gap-3">
                <h3 className="font-semibold text-slate-900">{t.name}</h3>
                <span className="text-sm text-slate-500">{t.duration_minutes} min</span>
              </div>
              {t.description && (
                <p className="mt-1 text-sm text-slate-600">{t.description}</p>
              )}
              {t.location_instructions && (
                <p className="mt-2 text-xs text-slate-500">{t.location_instructions}</p>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
