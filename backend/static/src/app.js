/* Minimal site-wide JS: mobile nav toggle + reveal-on-scroll. No
 * framework, no build step. Each block guards its own DOM lookup so a
 * page that doesn't use the feature pays no runtime cost. */
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

  /* Reveal-on-scroll. Any element marked `data-reveal` starts hidden
   * (initial state lives in styles.css). When it enters the viewport
   * we add `is-visible`, which triggers the keyframe animation defined
   * in tailwind.config.js. Honors prefers-reduced-motion by skipping
   * the observer and immediately revealing every node. */
  document.addEventListener("DOMContentLoaded", function () {
    var nodes = document.querySelectorAll("[data-reveal]");
    if (!nodes.length) {
      return;
    }

    var reduceMotion =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion || typeof window.IntersectionObserver !== "function") {
      nodes.forEach(function (n) {
        n.classList.add("is-visible");
      });
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) {
            return;
          }
          var el = entry.target;
          var stagger = parseInt(el.getAttribute("data-reveal-stagger"), 10);
          if (isNaN(stagger) || stagger < 0) {
            stagger = 0;
          }
          el.style.animationDelay = Math.min(stagger, 8) * 80 + "ms";
          el.classList.add("is-visible");
          observer.unobserve(el);
        });
      },
      { threshold: 0.18, rootMargin: "0px 0px -40px 0px" }
    );

    nodes.forEach(function (n) {
      observer.observe(n);
    });
  });
})();
