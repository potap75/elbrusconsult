export type AppointmentType = {
  slug: string;
  name: string;
  duration_minutes: number;
  description: string;
  location_instructions: string;
};

export type Service = {
  id: number;
  name: string;
  slug: string;
  tagline: string;
};

export type IslandProps = {
  appointmentTypesUrl: string;
  slotsUrl: string;
  bookingsUrl: string;
  bookingLookupUrl: string;
  servicesUrl: string;
  scheduleUrl: string;
  defaultTimezone: string;
  csrfToken: string;
  rescheduleToken: string | null;
};

export type BookingFormState = {
  name: string;
  email: string;
  company: string;
  phone: string;
  service: string;
  notes: string;
};

export const emptyForm: BookingFormState = {
  name: "",
  email: "",
  company: "",
  phone: "",
  service: "",
  notes: "",
};
