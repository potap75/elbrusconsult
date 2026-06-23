/* Minimal first-party consent banner wired to Google Consent Mode v2.
 *
 * Storage:
 *   localStorage["elb_consent"] = "granted" | "denied"  (no expiry; user
 *   re-resets by clearing site data)
 *
 * Events we push to dataLayer so GTM can react:
 *   { event: "consent_decision", consent_state: "granted" | "denied" }
 *
 * Why localStorage and not a cookie: this is purely a UI signal -- the
 * server doesn't need to read it, and a cookie would itself need consent
 * under some interpretations of ePrivacy. localStorage for a non-tracking
 * value (the literal string "granted" / "denied") is universally accepted.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "elb_consent";
  var GRANTED = "granted";
  var DENIED = "denied";

  function readDecision() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  function writeDecision(value) {
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch (e) {
      /* ignore -- private mode, quota, etc. */
    }
  }

  function pushUetConsent(state) {
    window.uetq = window.uetq || [];
    window.uetq.push("consent", "update", {
      ad_storage: state === GRANTED ? "granted" : "denied",
    });
  }

  function pushLinkedInInsight(state) {
    if (
      state === GRANTED &&
      typeof window.elbrusLoadLinkedInInsight === "function"
    ) {
      window.elbrusLoadLinkedInInsight();
    }
  }

  function pushConsentUpdate(state) {
    if (typeof window.gtag !== "function") {
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({
        event: "consent_decision",
        consent_state: state,
      });
      pushUetConsent(state);
      pushLinkedInInsight(state);
      return;
    }
    var payload = state === GRANTED
      ? {
          ad_storage: "granted",
          ad_user_data: "granted",
          ad_personalization: "granted",
          analytics_storage: "granted",
        }
      : {
          ad_storage: "denied",
          ad_user_data: "denied",
          ad_personalization: "denied",
          analytics_storage: "denied",
        };
    window.gtag("consent", "update", payload);
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: "consent_decision",
      consent_state: state,
    });
    pushUetConsent(state);
    pushLinkedInInsight(state);
  }

  function hide(banner) {
    banner.setAttribute("hidden", "");
  }

  function show(banner) {
    banner.removeAttribute("hidden");
  }

  document.addEventListener("DOMContentLoaded", function () {
    var banner = document.getElementById("elbrus-consent");
    if (!banner) {
      return;
    }

    var decision = readDecision();
    if (decision === GRANTED || decision === DENIED) {
      // Visitor decided previously; re-apply on every load so Consent Mode
      // is in the right state before any tag fires inside GTM.
      pushConsentUpdate(decision);
      return;
    }

    // No decision on file: show the banner. We rely on the server-rendered
    // `hidden` attribute keeping the banner off-screen during initial paint
    // so it can't cause CLS.
    show(banner);

    banner.addEventListener("click", function (event) {
      var target = event.target;
      if (!target || target.nodeType !== 1) {
        return;
      }
      var action = target.getAttribute("data-consent-action");
      if (action !== "accept" && action !== "reject") {
        return;
      }
      var state = action === "accept" ? GRANTED : DENIED;
      writeDecision(state);
      pushConsentUpdate(state);
      hide(banner);
    });
  });
})();
