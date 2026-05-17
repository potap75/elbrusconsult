import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createBooking,
  fetchAppointmentTypes,
  fetchServices,
  fetchSlots,
  lookupBooking,
} from "./api";
import {
  detectTimezone,
  localDayKey,
  ymd,
} from "./dateUtils";
import { StepAppointmentType } from "./StepAppointmentType";
import { StepCalendar } from "./StepCalendar";
import { StepTimes } from "./StepTimes";
import { StepDetails } from "./StepDetails";
import { StepDone } from "./StepDone";
import { Stepper } from "./Stepper";
import type { AppointmentType, BookingFormState, IslandProps, Service } from "./types";
import { emptyForm } from "./types";
import { endOfMonth, startOfMonth } from "date-fns";
import { toZonedTime } from "date-fns-tz";

type Step = 1 | 2 | 3 | 4 | 5;

type BookingResult = {
  manageUrl: string;
  slot: Date;
  appointmentType: AppointmentType;
};

export function App(props: IslandProps) {
  const [appointmentTypes, setAppointmentTypes] = useState<AppointmentType[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [appointmentType, setAppointmentType] = useState<AppointmentType | null>(null);
  const [form, setForm] = useState<BookingFormState>(emptyForm);
  const [step, setStep] = useState<Step>(1);
  const [timezone, setTimezone] = useState<string>(() =>
    detectTimezone(props.defaultTimezone),
  );
  const [monthAnchor, setMonthAnchor] = useState<Date>(() => new Date());
  const [slotsByDay, setSlotsByDay] = useState<Record<string, Date[]>>({});
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [selectedDayKey, setSelectedDayKey] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<Date | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [result, setResult] = useState<BookingResult | null>(null);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);

  const isReschedule = props.rescheduleToken !== null;

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchAppointmentTypes(props.appointmentTypesUrl),
      fetchServices(props.servicesUrl),
    ])
      .then(([types, svcs]) => {
        if (cancelled) return;
        setAppointmentTypes(types);
        setServices(svcs);
      })
      .catch(() => {
        if (!cancelled) setBootstrapError("We couldn't load the booking calendar. Please refresh or use the contact form.");
      });
    return () => {
      cancelled = true;
    };
  }, [props.appointmentTypesUrl, props.servicesUrl]);

  useEffect(() => {
    if (!props.rescheduleToken) return;
    let cancelled = false;
    lookupBooking(props.bookingLookupUrl, props.rescheduleToken).then((b) => {
      if (cancelled || !b) return;
      setForm({
        name: b.name,
        email: b.email,
        company: b.company,
        phone: b.phone,
        service: b.service ? String(b.service) : "",
        notes: b.notes,
      });
      if (b.customer_timezone) setTimezone(b.customer_timezone);
      const original = new Date(b.start_at);
      setMonthAnchor(original);
    });
    return () => {
      cancelled = true;
    };
  }, [props.bookingLookupUrl, props.rescheduleToken]);

  useEffect(() => {
    if (props.rescheduleToken && appointmentTypes.length > 0 && !appointmentType) {
      lookupBooking(props.bookingLookupUrl, props.rescheduleToken).then((b) => {
        if (!b) return;
        const match = appointmentTypes.find((t) => t.slug === b.appointment_type);
        if (match) setAppointmentType(match);
      });
    }
  }, [props.bookingLookupUrl, props.rescheduleToken, appointmentTypes, appointmentType]);

  const monthBounds = useMemo(() => {
    const localAnchor = toZonedTime(monthAnchor, timezone);
    return { from: ymd(startOfMonth(localAnchor)), to: ymd(endOfMonth(localAnchor)) };
  }, [monthAnchor, timezone]);

  useEffect(() => {
    if (!appointmentType) return;
    let cancelled = false;
    setLoadingSlots(true);
    fetchSlots(props.slotsUrl, {
      type: appointmentType.slug,
      from: monthBounds.from,
      to: monthBounds.to,
      rescheduleToken: props.rescheduleToken,
    })
      .then((slots) => {
        if (cancelled) return;
        const grouped: Record<string, Date[]> = {};
        for (const s of slots) {
          const key = localDayKey(s, timezone);
          (grouped[key] ??= []).push(s);
        }
        setSlotsByDay(grouped);
      })
      .catch(() => {
        if (!cancelled) setSlotsByDay({});
      })
      .finally(() => {
        if (!cancelled) setLoadingSlots(false);
      });
    return () => {
      cancelled = true;
    };
  }, [appointmentType, props.slotsUrl, props.rescheduleToken, monthBounds.from, monthBounds.to, timezone]);

  const handlePickType = useCallback((t: AppointmentType) => {
    setAppointmentType(t);
    setSelectedDayKey(null);
    setSelectedSlot(null);
    setSlotsByDay({});
    setStep(2);
  }, []);

  const handlePickDay = useCallback((key: string) => {
    setSelectedDayKey(key);
    setSelectedSlot(null);
    setStep(3);
  }, []);

  const handlePickSlot = useCallback((slot: Date) => {
    setSelectedSlot(slot);
    setStep(4);
  }, []);

  const handleUpdate = useCallback((key: keyof BookingFormState, value: string) => {
    setForm((f) => ({ ...f, [key]: value }));
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!appointmentType || !selectedSlot) return;
    setSubmitting(true);
    setError(null);
    setFieldErrors({});
    const response = await createBooking(props.bookingsUrl, props.csrfToken, {
      appointment_type: appointmentType.slug,
      start_at: selectedSlot.toISOString(),
      name: form.name.trim(),
      email: form.email.trim(),
      company: form.company.trim(),
      phone: form.phone.trim(),
      service: form.service ? Number(form.service) : null,
      notes: form.notes.trim(),
      customer_timezone: timezone,
      reschedule_token: props.rescheduleToken,
    });
    setSubmitting(false);
    if (response.ok) {
      setResult({
        manageUrl: response.data.manage_url,
        slot: new Date(response.data.start_at),
        appointmentType,
      });
      setStep(5);
      return;
    }
    if (response.status === 409) {
      setError(response.data.message ?? "That time was just booked. Please pick another.");
      setSelectedSlot(null);
      setStep(3);
      return;
    }
    if (response.data.fields) {
      setFieldErrors(response.data.fields);
    }
    setError(
      response.data.error === "validation_error"
        ? "Please double-check the highlighted fields."
        : response.data.message ?? "Something went wrong. Please try again.",
    );
  }, [
    appointmentType,
    selectedSlot,
    form,
    timezone,
    props.bookingsUrl,
    props.csrfToken,
    props.rescheduleToken,
  ]);

  if (bootstrapError) {
    return (
      <div className="rounded-md border border-rose-300 bg-rose-50 px-4 py-3 text-rose-800">
        {bootstrapError}
      </div>
    );
  }

  if (step === 5 && result) {
    return (
      <StepDone
        appointmentType={result.appointmentType}
        slot={result.slot}
        timezone={timezone}
        manageUrl={result.manageUrl}
        isReschedule={isReschedule}
      />
    );
  }

  const slotsForSelected =
    selectedDayKey !== null ? slotsByDay[selectedDayKey] ?? [] : [];

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6 sm:p-8 shadow-sm">
      <Stepper current={step <= 4 ? (step as 1 | 2 | 3 | 4) : 4} />

      {isReschedule && (
        <div className="mb-4 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          You're rescheduling an existing booking. Pick a new time below.
        </div>
      )}

      {step === 1 && (
        <StepAppointmentType
          appointmentTypes={appointmentTypes}
          selected={appointmentType}
          onPick={handlePickType}
        />
      )}

      {step === 2 && appointmentType && (
        <>
          <BackButton onClick={() => setStep(1)} label="Change appointment type" />
          <StepCalendar
            timezone={timezone}
            selectedDayKey={selectedDayKey}
            loading={loadingSlots}
            slotsByDay={slotsByDay}
            monthAnchor={monthAnchor}
            onMonthChange={setMonthAnchor}
            onPickDay={handlePickDay}
          />
        </>
      )}

      {step === 3 && appointmentType && selectedDayKey && (
        <>
          <BackButton onClick={() => setStep(2)} label="Change date" />
          <StepTimes
            dayKey={selectedDayKey}
            slots={slotsForSelected}
            timezone={timezone}
            selectedSlot={selectedSlot}
            onPickSlot={handlePickSlot}
            onChangeTimezone={setTimezone}
          />
        </>
      )}

      {step === 4 && appointmentType && selectedSlot && (
        <>
          <BackButton onClick={() => setStep(3)} label="Change time" />
          <StepDetails
            appointmentType={appointmentType}
            slot={selectedSlot}
            timezone={timezone}
            form={form}
            services={services}
            fieldErrors={fieldErrors}
            submitting={submitting}
            errorMessage={error}
            onUpdate={handleUpdate}
            onSubmit={handleSubmit}
          />
        </>
      )}
    </div>
  );
}

function BackButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mb-4 inline-flex items-center text-sm text-summit-700 hover:text-summit-900"
    >
      &larr; {label}
    </button>
  );
}
