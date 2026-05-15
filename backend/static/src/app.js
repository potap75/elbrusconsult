/* Minimal site-wide JS: mobile nav toggle. No framework, no build step. */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var toggle = document.querySelector("[data-nav-toggle]");
    var mobileMenu = document.querySelector("[data-nav-mobile]");

    if (!toggle || !mobileMenu) {
      return;
    }

    toggle.addEventListener("click", function () {
      var expanded = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", expanded ? "false" : "true");
      mobileMenu.classList.toggle("hidden");
    });
  });
})();
