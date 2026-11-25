/* Superwebby cookie-banner janitor.
 * Prefers explicit "reject / necessary only" controls from known CMPs.
 * Falls back to hiding leftover banner chrome. Never clicks "accept all".
 */
(function () {
  if (window.__superwebbyCookieJanitor) return;
  window.__superwebbyCookieJanitor = true;

  var REJECT_RE = /^\s*(reject all|reject|decline all|decline|refuse all|refuse|deny all|deny|necessary only|only necessary|essential only|use necessary|save (and exit|without accepting)|do not (accept|consent|sell)|disagree|opt out|opt-out|ich lehne ab|ablehnen|nur notwendige|nur essenzielle|tout refuser|refuser|rejeter|rechazar (todo|todos)?|solo necesarias|rifiuta( tutto)?|solo necessari|afwijzen|weigeren|tylko niezbędne|odmítnout|avvisa alla|nega)\s*$/i;

  var SELECTORS = [
    "#onetrust-reject-all-handler",
    "button#onetrust-reject-all-handler",
    "#onetrust-pc-sdk .ot-pc-refuse-all-handler",
    "#CybotCookiebotDialogBodyButtonDecline",
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinDeclineAll",
    "#CybotCookiebotDialogBodyButtonDeclineAll",
    "#didomi-notice-disagree-button",
    "button#didomi-notice-disagree-button",
    "#tarteaucitronAllDenied2",
    "button.fc-cta-do-not-consent",
    "button.fc-button.fc-cta-do-not-consent",
    ".fc-consent-root button[aria-label='Consent', i]",
    "#sp-cc-rejectall-link",
    "button[id*='reject-all' i]",
    "button[id*='rejectall' i]",
    "button[class*='reject-all' i]",
    "button[data-testid*='reject-all' i]",
    "button[aria-label*='Reject all' i]",
    "button[aria-label*='Decline' i]",
    "#notice-cookie-block-btn-decline",
    ".cc-deny",
    ".cc-dismiss",
    "button.cookie-reject",
    "button[mode='secondary'].qc-cmp2-summary-buttons",
    ".qc-cmp2-footer button[mode='secondary']",
    "#qc-cmp2-ui button[mode='secondary']",
    "button.iubenda-cs-reject-btn",
    "button.cky-btn-reject",
    ".cky-consent-bar .cky-btn-reject",
    "#cookieyes-reject",
    "button#truste-consent-required",
    "#consent-decline",
    ".js-consent-reject",
    "button[data-role='rejectAll']",
    "button[data-action='reject-all']",
    "button[data-cookie-refuse]",
    "a.cc-btn.cc-deny",
    "#usercentrics-root button[data-testid='uc-deny-all-button']",
    "button#uc-btn-deny-banner",
    ".osano-cm-denyAll",
    ".osano-cm-button--type_denyAll",
    "button#ez-cookie-dialog-decline",
    "button.cookie-bar-decline-btn"
  ];

  var HIDE_SELECTORS = [
    "#onetrust-banner-sdk",
    "#onetrust-consent-sdk .onetrust-pc-dark-filter",
    "#CybotCookiebotDialog, #CybotCookiebotDialogBodyUnderlay",
    "#didomi-host, .didomi-popup-container, #didomi-notice",
    ".qc-cmp2-container, .qc-cmp2-overlay",
    ".fc-consent-root",
    ".cc-window, .cc-overlay",
    "#cookie-law-info-bar",
    ".cookie-banner, .cookieBanner, .CookieBanner",
    ".js-cookie-banner",
    "#cookieBanner",
    "#cookie-banner",
    ".eu-cookie-compliance-banner",
    "#tarteaucitronRoot",
    ".osano-cm-window, .osano-cm-dialog"
  ];

  function visible(el) {
    if (!el) return false;
    var s = window.getComputedStyle(el);
    if (s.display === "none" || s.visibility === "hidden" || s.opacity === "0") return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function click(el) {
    if (!el || !visible(el) || el.disabled) return false;
    try {
      el.click();
      return true;
    } catch (e) {
      return false;
    }
  }

  function textOf(el) {
    return ((el.innerText || el.textContent || el.getAttribute("aria-label") || el.value || "") + "").replace(/\s+/g, " ").trim();
  }

  function inCookieContext(el) {
    var n = el, hops = 0;
    while (n && hops < 8) {
      var idc = ((n.id || "") + " " + (n.className || "")).toLowerCase();
      if (/cookie|consent|gdpr|cmp|onetrust|didomi|cookiebot|usercentrics|osano|tarteaucitron/.test(idc)) {
        return true;
      }
      n = n.parentElement;
      hops++;
    }
    return false;
  }

  function pass() {
    var i, el, list, clicked = false;
    for (i = 0; i < SELECTORS.length; i++) {
      try {
        list = document.querySelectorAll(SELECTORS[i]);
      } catch (e) {
        continue;
      }
      for (var j = 0; j < list.length; j++) {
        if (click(list[j])) clicked = true;
      }
    }
    if (clicked) return true;

    var candidates = document.querySelectorAll("button, a[role='button'], input[type='button'], input[type='submit']");
    for (i = 0; i < candidates.length; i++) {
      el = candidates[i];
      if (!visible(el)) continue;
      var t = textOf(el);
      if (!t || t.length > 48) continue;
      if (REJECT_RE.test(t) && inCookieContext(el)) {
        if (click(el)) return true;
      }
    }
    return false;
  }

  function hideLeftovers() {
    for (var i = 0; i < HIDE_SELECTORS.length; i++) {
      var list;
      try {
        list = document.querySelectorAll(HIDE_SELECTORS[i]);
      } catch (e) {
        continue;
      }
      for (var j = 0; j < list.length; j++) {
        var el = list[j];
        if (!visible(el)) continue;
        el.style.setProperty("display", "none", "important");
        el.style.setProperty("visibility", "hidden", "important");
        el.setAttribute("aria-hidden", "true");
      }
    }
    try {
      if (document.body && /^(hidden|scroll)$/.test(document.body.style.overflow)) {
        document.body.style.removeProperty("overflow");
      }
    } catch (e) {}
  }

  var tries = 0;
  function tick() {
    tries++;
    var ok = pass();
    if (!ok && tries >= 3) hideLeftovers();
    if (tries < 8) setTimeout(tick, tries < 3 ? 400 : 1200);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { setTimeout(tick, 50); });
  } else {
    setTimeout(tick, 50);
  }
})();
