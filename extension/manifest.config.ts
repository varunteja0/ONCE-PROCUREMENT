import { defineManifest } from "@crxjs/vite-plugin";

const HOST_PERMISSIONS: string[] = [
  "*://*.appliedepic.com/*",
  "*://*.amtrustfinancial.com/*",
  "*://*.markel.com/*",
  "*://*.ams360.com/*",
  "*://*.sircon.com/*",
];

// API origins the background service worker needs to reach via fetch().
// Kept separate from `HOST_PERMISSIONS` (which is also the
// content-script match list) so the API origins do not accidentally
// trigger content-script injection on the backend itself.
const API_HOST_PERMISSIONS: string[] = [
  "http://localhost:8000/*", // dev backend — Once API
  "https://api.getonce.com/*", // prod backend — see docs/DEPLOY.md
];

export default defineManifest({
  manifest_version: 3,
  name: "Once — Supplier Portal Autopilot",
  description:
    "Automates insurance supplier portal submissions with a tamper-evident receipt for every action.",
  version: "0.1.0",
  action: {
    default_popup: "src/popup/popup.html",
    default_title: "Once — Supplier Portal Autopilot",
  },
  background: {
    service_worker: "src/background/index.ts",
    type: "module",
  },
  options_page: "src/options/options.html",
  // PERMISSIONS — each one justified in extension/README.md
  //  storage   : tokens, API base, auto-lock prefs, default-supplier-per-portal
  //  activeTab : send PORTAL_FILL to current tab on user gesture
  //  scripting : programmatic content-script re-injection on options/popup actions
  //  alarms    : periodic sync (5m), pending-retry (30s), lock check (1m)
  //  idle      : drive auto-lock from chrome.idle when the user goes away
  //  tabs      : tabs.onUpdated → portal detection + badge text
  permissions: ["storage", "activeTab", "scripting", "alarms", "idle", "tabs"],
  host_permissions: [...HOST_PERMISSIONS, ...API_HOST_PERMISSIONS],
  content_scripts: [
    {
      matches: HOST_PERMISSIONS,
      js: ["src/content/dispatcher.ts"],
      run_at: "document_idle",
      all_frames: false,
    },
  ],
});
