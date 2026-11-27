// Superwebby YouTube / YouTube Music ad remover.
// Runs at document creation in the page's main world on youtube.com and
// music.youtube.com. Always on, including High Speed mode.
(function () {
  "use strict";
  var host = location.hostname;
  if (!/(^|\.)youtube\.com$|(^|\.)youtube-nocookie\.com$/.test(host)) return;
  if (window.__superwebbyYtAds) return;
  window.__superwebbyYtAds = true;

  var AD_KEYS = ["adPlacements", "playerAds", "adSlots", "adBreakHeartbeatParams",
                 "adBreakParams", "adSafetyReason"];

  function strip(obj, depth) {
    if (!obj || typeof obj !== "object" || depth > 6) return obj;
    try {
      for (var i = 0; i < AD_KEYS.length; i++) {
        if (Object.prototype.hasOwnProperty.call(obj, AD_KEYS[i])) delete obj[AD_KEYS[i]];
      }
      if (obj.playerResponse) strip(obj.playerResponse, depth + 1);
      if (Array.isArray(obj)) {
        for (var j = 0; j < obj.length; j++) strip(obj[j], depth + 1);
      } else if (obj.response) {
        strip(obj.response, depth + 1);
      }
    } catch (e) {}
    return obj;
  }

  // 1. Strip ads from the inline initial player response.
  function guardGlobal(name) {
    var value = window[name];
    try {
      Object.defineProperty(window, name, {
        configurable: true,
        get: function () { return value; },
        set: function (v) { value = strip(v, 0); }
      });
      if (value) strip(value, 0);
    } catch (e) {}
  }
  guardGlobal("ytInitialPlayerResponse");

  // 2. Strip ads from any JSON the player parses (covers SPA navigations).
  var origParse = JSON.parse;
  JSON.parse = function () {
    var out = origParse.apply(this, arguments);
    if (out && typeof out === "object" && (out.adPlacements || out.playerAds ||
        out.adSlots || (out.playerResponse && out.playerResponse.adPlacements))) {
      strip(out, 0);
    }
    return out;
  };

  // 3. Strip ads from youtubei/v1/player fetch responses.
  var origFetch = window.fetch;
  if (origFetch) {
    window.fetch = function (input, init) {
      var url = typeof input === "string" ? input : (input && input.url) || "";
      var p = origFetch.apply(this, arguments);
      if (url.indexOf("/youtubei/v1/player") === -1) return p;
      if (url.indexOf("/ad_break") !== -1) {
        return Promise.resolve(new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }));
      }
      return p.then(function (resp) {
        try {
          return resp.clone().json().then(function (data) {
            strip(data, 0);
            return new Response(JSON.stringify(data), {
              status: resp.status, statusText: resp.statusText, headers: resp.headers
            });
          }).catch(function () { return resp; });
        } catch (e) { return resp; }
      });
    };
  }

  // 4. Remove ad slots from the DOM and skip anything that still plays.
  var CSS = [
    "ytd-ad-slot-renderer", "ytd-in-feed-ad-layout-renderer", "ytd-banner-promo-renderer",
    "ytd-promoted-sparkles-web-renderer", "ytd-display-ad-renderer", "ytd-player-legacy-desktop-watch-ads-renderer",
    "ytd-companion-slot-renderer", "ytd-action-companion-ad-renderer", "ytd-statement-banner-renderer",
    "ytd-rich-item-renderer:has(> #content > ytd-ad-slot-renderer)",
    "#masthead-ad", "#player-ads", ".ytp-ad-module", ".ytp-ad-overlay-container", ".ytp-ad-image-overlay",
    "ytmusic-mealbar-promo-renderer", "ytmusic-statement-banner-renderer",
    "ytmusic-player-bar .ytp-ad-overlay-slot", "tp-yt-paper-dialog:has(ytmusic-mealbar-promo-renderer)"
  ].join(",") + "{display:none!important}";

  function injectCss() {
    if (document.getElementById("superwebby-yt-css")) return;
    var style = document.createElement("style");
    style.id = "superwebby-yt-css";
    style.textContent = CSS;
    (document.head || document.documentElement).appendChild(style);
  }

  function skip() {
    try {
      var player = document.querySelector(".html5-video-player");
      if (player && (player.classList.contains("ad-showing") || player.classList.contains("ad-interrupting"))) {
        var video = player.querySelector("video");
        if (video && isFinite(video.duration) && video.duration > 0) {
          video.muted = true;
          video.currentTime = video.duration;
        }
      }
      var btn = document.querySelector(".ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button, button[id^='skip-button']");
      if (btn) btn.click();
      var close = document.querySelector(".ytp-ad-overlay-close-button");
      if (close) close.click();
    } catch (e) {}
  }

  injectCss();
  document.addEventListener("DOMContentLoaded", injectCss);
  var mo = new MutationObserver(function () { skip(); });
  function observe() {
    if (document.documentElement) {
      mo.observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
    }
  }
  observe();
  setInterval(skip, 500);
})();
