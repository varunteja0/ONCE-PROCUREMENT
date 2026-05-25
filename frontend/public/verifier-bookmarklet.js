/*
 * Once receipt-verifier bookmarklet (vanilla JS, no dependencies).
 *
 * Prompts for a Once receipt ID, fetches the canonical verification result
 * from getonce.com, and renders a small fixed overlay with the verdict.
 *
 * Source is served verbatim at /verifier-bookmarklet.js — read it before
 * you install it. The bookmarklet only ever calls the documented public
 * endpoint and never sends auth.
 */
(function () {
  "use strict";

  var BACKEND = "https://getonce.com";

  function prompt_id() {
    return window.prompt("Once receipt ID (e.g. rcpt_...):", "");
  }

  function paint(verified, payload) {
    var existing = document.getElementById("once-verifier-overlay");
    if (existing) existing.remove();
    var wrap = document.createElement("div");
    wrap.id = "once-verifier-overlay";
    wrap.style.cssText = [
      "position:fixed",
      "top:16px",
      "right:16px",
      "z-index:2147483647",
      "max-width:380px",
      "padding:16px 18px",
      "border-radius:8px",
      "box-shadow:0 6px 24px rgba(0,0,0,0.18)",
      "font-family:system-ui,-apple-system,Segoe UI,sans-serif",
      "font-size:13px",
      "line-height:1.4",
      "color:#0f172a",
      "background:" + (verified ? "#ecfdf5" : "#fef2f2"),
      "border:1px solid " + (verified ? "#6ee7b7" : "#fca5a5"),
    ].join(";");

    var title = document.createElement("div");
    title.style.cssText = "font-weight:600;font-size:14px;margin-bottom:6px";
    title.textContent = verified ? "✓ Once receipt: VALID" : "✗ Once receipt: INVALID";
    wrap.appendChild(title);

    if (payload && payload.receipt) {
      var meta = document.createElement("div");
      meta.style.cssText = "font-family:ui-monospace,monospace;font-size:11px;color:#334155;word-break:break-all";
      meta.innerHTML =
        "<div>id: " +
        escape_html(payload.receipt.receipt_id) +
        "</div>" +
        "<div>key: " +
        escape_html(payload.receipt.signing_key_id) +
        "</div>" +
        "<div>at: " +
        escape_html(payload.receipt.submitted_at) +
        "</div>";
      wrap.appendChild(meta);
    }
    if (payload && payload.reason) {
      var reason = document.createElement("div");
      reason.style.cssText = "margin-top:6px;color:#7f1d1d";
      reason.textContent = payload.reason;
      wrap.appendChild(reason);
    }

    var close = document.createElement("button");
    close.textContent = "×";
    close.setAttribute("aria-label", "Close");
    close.style.cssText =
      "position:absolute;top:6px;right:8px;border:none;background:transparent;font-size:18px;cursor:pointer;color:#64748b";
    close.onclick = function () {
      wrap.remove();
    };
    wrap.appendChild(close);

    document.body.appendChild(wrap);
  }

  function escape_html(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  var id = prompt_id();
  if (!id) return;
  id = id.trim();
  if (!id) return;

  fetch(BACKEND + "/v1/verify/" + encodeURIComponent(id), {
    credentials: "omit",
    cache: "no-store",
  })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (json) {
      paint(Boolean(json && json.verified), json);
    })
    .catch(function (err) {
      paint(false, { reason: "Verifier error: " + (err && err.message ? err.message : err) });
    });
})();
