import { useEffect } from "react";
import type { AppointmentType } from "./types";
import { formatLongDate, formatTime } from "./dateUtils";

type Props = {
  appointmentType: AppointmentType;
  slot: Date;
  timezone: string;
  manageUrl: string;
  isReschedule: boolean;
};

// `window.elbrusTrack` is the single client-side conversion API; it pushes
// a normalised event onto dataLayer, where GTM fans it out to Google Ads /
// LinkedIn / Meta / Microsoft / TikTok / GA4. Declared loose because the
// shim is injected at runtime by base.html and may be missing in tests.
declare global {
  interface Window {
    elbrusTrack?: (name: string, payload?: Record<string, unknown>) => void;
  }
}

export function StepDone({
  appointmentType,
  slot,
  timezone,
  manageUrl,
  isReschedule,
}: Props) {
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.elbrusTrack !== "function") {
      return;
    }
    window.elbrusTrack(
      isReschedule ? "booking_rescheduled" : "booking_created",
      {
        appointment_type: appointmentType.slug,
        duration_minutes: appointmentType.duration_minutes,
        timezone,
        conversion_type: "booking",
      },
    );
    // Run exactly once per success render. The slot Date is the natural
    // identity here, but we'd rather over-fire on remounts than risk
    // missing a conversion, so deps stay empty.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
