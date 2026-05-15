import { useEffect, useMemo, useState } from "react";

type Service = {
  id: number;
  name: string;
  slug: string;
  tagline: string;
};

type Props = {
  servicesUrl: string;
  inquiryUrl: string;
  csrfToken: string;
};

type FormState = {
  name: string;
  email: string;
  company: string;
  phone: string;
  service: string;
  preferred_date: string;
  timezone_label: string;
  notes: string;
};

const initialForm: FormState = {
  name: "",
  email: "",
  company: "",
  phone: "",
  service: "",
  preferred_date: "",
  timezone_label: "",
  notes: "",
};

export function App({ servicesUrl, inquiryUrl, csrfToken }: Props) {
  const [services, setServices] = useState<Service[]>([]);
  const [form, setForm] = useState<FormState>(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  const detectedTz = useMemo(() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    } catch {
      return "";
    }
  }, []);

  useEffect(() => {
    setForm((f) => (f.timezone_label ? f : { ...f, timezone_label: detectedTz }));
  }, [detectedTz]);

  useEffect(() => {
    let cancelled = false;
    fetch(servicesUrl, { headers: { Accept: "application/json" } })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("services_unavailable"))))
      .then((data: { services: Service[] }) => {
        if (!cancelled) setServices(data.services ?? []);
      })
      .catch(() => {
        // Non-fatal: form still works without the picker populated.
      });
    return () => {
      cancelled = true;
    };
  }, [servicesUrl]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setFieldErrors({});

    try {
      const payload = {
        ...form,
        service: form.service ? Number(form.service) : null,
        preferred_date: form.preferred_date || null,
      };
      const response = await fetch(inquiryUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(payload),
      });
      if (response.ok) {
        setSubmitted(true);
        setForm(initialForm);
        return;
      }
      const body = (await response.json().catch(() => ({}))) as {
        error?: string;
        fields?: Record<string, string[]>;
      };
      if (body.fields) {
        setFieldErrors(body.fields);
      }
      setError(
        body.error === "validation_error"
          ? "Please double-check the highlighted fields."
          : "Something went wrong. Please try again or use the contact form.",
      );
    } catch {
      setError("Network error - please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="rounded-lg border border-summit-300 bg-summit-50 p-6 text-summit-900">
        <h2 className="text-xl font-semibold">Thanks - we got your request.</h2>
        <p className="mt-2">
          A consultant will reach out shortly to confirm a time. In the meantime,
          feel free to read the blog or explore our services.
        </p>
      </div>
    );
  }

  const inputClass =
    "mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-summit-500 focus:border-summit-500";

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border border-slate-200 bg-white p-8 shadow-sm grid grid-cols-1 md:grid-cols-2 gap-6"
      noValidate
    >
      <div className="md:col-span-2">
        <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <strong>Booking coming soon.</strong> Self-service calendar availability
          is on the roadmap. Send us your details and we will follow up to confirm
          a time with a senior consultant.
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="sched-name">
          Name
        </label>
        <input
          id="sched-name"
          className={inputClass}
          type="text"
          required
          autoComplete="name"
          value={form.name}
          onChange={(e) => update("name", e.target.value)}
        />
        {fieldErrors.name?.[0] && (
          <p className="mt-1 text-sm text-rose-600">{fieldErrors.name[0]}</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="sched-email">
          Email
        </label>
        <input
          id="sched-email"
          className={inputClass}
          type="email"
          required
          autoComplete="email"
          value={form.email}
          onChange={(e) => update("email", e.target.value)}
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
          onChange={(e) => update("company", e.target.value)}
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="sched-phone">
          Phone (optional)
        </label>
        <input
          id="sched-phone"
          className={inputClass}
          type="tel"
          autoComplete="tel"
          value={form.phone}
          onChange={(e) => update("phone", e.target.value)}
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="sched-service">
          Service
        </label>
        <select
          id="sched-service"
          className={inputClass}
          value={form.service}
          onChange={(e) => update("service", e.target.value)}
        >
          <option value="">Choose a service...</option>
          {services.map((s) => (
            <option key={s.id} value={String(s.id)}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="sched-date">
          Preferred date
        </label>
        <input
          id="sched-date"
          className={inputClass}
          type="date"
          value={form.preferred_date}
          onChange={(e) => update("preferred_date", e.target.value)}
        />
      </div>

      <div className="md:col-span-2">
        <label className="block text-sm font-medium text-slate-700" htmlFor="sched-tz">
          Your timezone
        </label>
        <input
          id="sched-tz"
          className={inputClass}
          type="text"
          value={form.timezone_label}
          onChange={(e) => update("timezone_label", e.target.value)}
          placeholder="e.g. America/New_York"
        />
      </div>

      <div className="md:col-span-2">
        <label className="block text-sm font-medium text-slate-700" htmlFor="sched-notes">
          Notes
        </label>
        <textarea
          id="sched-notes"
          className={inputClass}
          rows={5}
          placeholder="Tell us about the engagement: scope, urgency, environments..."
          value={form.notes}
          onChange={(e) => update("notes", e.target.value)}
        />
      </div>

      {error && (
        <div className="md:col-span-2 rounded-md border border-rose-300 bg-rose-50 px-4 py-3 text-rose-800">
          {error}
        </div>
      )}

      <div className="md:col-span-2 flex items-center justify-between">
        <p className="text-xs text-slate-500">We typically respond within one business day.</p>
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex items-center rounded-md bg-summit-600 px-5 py-3 text-white font-semibold hover:bg-summit-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Sending..." : "Request a time"}
        </button>
      </div>
    </form>
  );
}
