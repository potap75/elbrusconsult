import type { AppointmentType, Service } from "./types";

export type ApiBooking = {
  manage_token: string;
  status: string;
  appointment_type: string;
  appointment_type_name: string;
  duration_minutes: number;
  name: string;
  email: string;
  company: string;
  phone: string;
  notes: string;
  service: number | null;
  start_at: string;
  end_at: string;
  customer_timezone: string;
};

export async function fetchAppointmentTypes(url: string): Promise<AppointmentType[]> {
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error("appointment_types_unavailable");
  const data = (await r.json()) as { appointment_types: AppointmentType[] };
  return data.appointment_types ?? [];
}

export async function fetchServices(url: string): Promise<Service[]> {
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok) return [];
  const data = (await r.json()) as { services: Service[] };
  return data.services ?? [];
}

export async function fetchSlots(
  url: string,
  params: { type: string; from: string; to: string; rescheduleToken?: string | null },
): Promise<Date[]> {
  const q = new URLSearchParams({
    type: params.type,
    from: params.from,
    to: params.to,
  });
  if (params.rescheduleToken) q.set("reschedule", params.rescheduleToken);
  const r = await fetch(`${url}?${q.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!r.ok) throw new Error("slots_unavailable");
  const data = (await r.json()) as { slots: string[] };
  return (data.slots ?? []).map((iso) => new Date(iso));
}

export type CreateBookingPayload = {
  appointment_type: string;
  start_at: string;
  name: string;
  email: string;
  company?: string;
  phone?: string;
  service?: number | null;
  notes?: string;
  customer_timezone: string;
  reschedule_token?: string | null;
};

export type CreateBookingResponse = {
  ok: true;
  id: number;
  manage_token: string;
  manage_url: string;
  start_at: string;
  end_at: string;
};

export type CreateBookingError = {
  error: string;
  message?: string;
  fields?: Record<string, string[]>;
};

export async function createBooking(
  url: string,
  csrfToken: string,
  payload: CreateBookingPayload,
): Promise<{ ok: true; data: CreateBookingResponse } | { ok: false; status: number; data: CreateBookingError }> {
  const r = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (r.ok) {
    return { ok: true, data: (await r.json()) as CreateBookingResponse };
  }
  const body = (await r.json().catch(() => ({ error: "unknown" }))) as CreateBookingError;
  return { ok: false, status: r.status, data: body };
}

export async function lookupBooking(url: string, token: string): Promise<ApiBooking | null> {
  const q = new URLSearchParams({ token });
  const r = await fetch(`${url}?${q.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!r.ok) return null;
  const data = (await r.json()) as { booking: ApiBooking };
  return data.booking ?? null;
}
