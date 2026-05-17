import type { AppointmentType } from "./types";
import { formatLongDate, formatTime } from "./dateUtils";

type Props = {
  appointmentType: AppointmentType;
  slot: Date;
  timezone: string;
  manageUrl: string;
  isReschedule: boolean;
};

export function StepDone({
  appointmentType,
  slot,
  timezone,
  manageUrl,
  isReschedule,
}: Props) {
  return (
    <div className="rounded-lg border border-summit-300 bg-summit-50 p-6 text-summit-900">
      <h2 className="text-xl font-semibold">
        {isReschedule ? "Booking moved." : "You're booked."}
      </h2>
      <p className="mt-2">
        <strong>{appointmentType.name}</strong> on{" "}
        {formatLongDate(slot, timezone)} at {formatTime(slot, timezone)} ({timezone}).
      </p>
      <p className="mt-2">
        A confirmation email with a calendar invite is on its way.
      </p>
      <p className="mt-4">
        Need to make a change?{" "}
        <a className="underline font-medium" href={manageUrl}>
          Manage your booking
        </a>
        .
      </p>
    </div>
  );
}
