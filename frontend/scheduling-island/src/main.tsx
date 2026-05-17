import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import type { IslandProps } from "./types";

const mount = document.getElementById("schedule-root");
if (mount) {
  const params = new URLSearchParams(window.location.search);
  const rescheduleToken = params.get("reschedule");

  const props: IslandProps = {
    appointmentTypesUrl:
      mount.dataset.appointmentTypesUrl ?? "/schedule/api/appointment-types/",
    slotsUrl: mount.dataset.slotsUrl ?? "/schedule/api/slots/",
    bookingsUrl: mount.dataset.bookingsUrl ?? "/schedule/api/bookings/",
    bookingLookupUrl:
      mount.dataset.bookingLookupUrl ?? "/schedule/api/bookings/lookup/",
    servicesUrl: mount.dataset.servicesUrl ?? "/schedule/api/services/",
    scheduleUrl: mount.dataset.scheduleUrl ?? "/schedule/",
    defaultTimezone: mount.dataset.defaultTimezone ?? "UTC",
    csrfToken: mount.dataset.csrfToken ?? "",
    rescheduleToken: rescheduleToken && rescheduleToken.length > 0 ? rescheduleToken : null,
  };
  createRoot(mount).render(
    <React.StrictMode>
      <App {...props} />
    </React.StrictMode>,
  );
}
