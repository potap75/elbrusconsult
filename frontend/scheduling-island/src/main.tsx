import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

const mount = document.getElementById("schedule-root");
if (mount) {
  const props = {
    servicesUrl: mount.dataset.servicesUrl ?? "/schedule/api/services/",
    inquiryUrl: mount.dataset.inquiryUrl ?? "/schedule/api/inquiry/",
    csrfToken: mount.dataset.csrfToken ?? "",
  };
  createRoot(mount).render(
    <React.StrictMode>
      <App {...props} />
    </React.StrictMode>,
  );
}
