import { useEffect, useState } from "react";
import { Camera, CheckCircle2, Loader2, Send, ShieldAlert } from "lucide-react";

import { send, sendToTab } from "../../lib/messaging";
import { getProfile } from "../../lib/vault";
import { usePopupStore, selectActiveSupplier } from "../../lib/store";
import { getCachedPortals } from "../../lib/sync";
import { getConsentForPortal } from "../../lib/api";
import type { SupplierListItem } from "../../lib/api";
import type { PortalDetection } from "../../lib/messaging";

interface Props {
  suppliers: SupplierListItem[];
  detection: PortalDetection | null;
}

export function Home({ suppliers, detection }: Props): JSX.Element {
  const tabId = usePopupStore((s) => s.tabId);
  const active = usePopupStore(selectActiveSupplier);
  const setActive = usePopupStore((s) => s.setActiveSupplier);
  const setBanner = usePopupStore((s) => s.setBanner);

  const [filling, setFilling] = useState(false);
  const [capturing, setCapturing] = useState(false);

  // Pick a default supplier if none selected yet — first one in the list.
  useEffect(() => {
    if (tabId !== null && active === null && suppliers.length > 0) {
      const first = suppliers[0];
      if (first) setActive(tabId, first.id);
    }
  }, [tabId, active, suppliers, setActive]);

  const activeSupplier = suppliers.find((s) => s.id === active) ?? null;

  const onFill = async (): Promise<void> => {
    if (!tabId || !detection || !activeSupplier) {
      setBanner({ kind: "error", text: "Select a supplier and load a supported portal page." });
      return;
    }
    setFilling(true);
    try {
      // Profile is keyed by supplier id in the vault. Fall back to "default"
      // when nothing has been stored yet so first-run still works.
      const profile =
        (await getProfile(activeSupplier.id)) ??
        (await getProfile("default"));
      if (!profile) {
        setBanner({
          kind: "error",
          text: "No profile in the vault. Save one from the web app first.",
        });
        return;
      }
      const resp = await sendToTab(tabId, {
        type: "content.fill",
        profile,
        portal: detection.portal,
      });
      if (!resp.ok) {
        setBanner({ kind: "error", text: `Fill failed: ${resp.error}` });
        return;
      }
      setBanner({
        kind: "success",
        text: `Filled ${resp.filled} field(s), skipped ${resp.skipped}.`,
      });
      await send({
        type: "portal.fill",
        tabId,
        supplierId: activeSupplier.id,
        portal: detection.portal,
        profile,
      });
    } catch (err) {
      setBanner({
        kind: "error",
        text: err instanceof Error ? err.message : "fill_failed",
      });
    } finally {
      setFilling(false);
    }
  };

  const onCapture = async (): Promise<void> => {
    if (!detection || !activeSupplier) {
      setBanner({ kind: "error", text: "Select a supplier and load a supported portal page." });
      return;
    }
    setCapturing(true);
    try {
      // Resolve the portal_id (DB UUID) from the platform string the
      // content-script reported. The portals list is cached by syncNow.
      const portals = await getCachedPortals();
      const portal = portals.find((p) => p.platform === detection.portal);
      if (!portal) {
        setBanner({
          kind: "error",
          text: `Portal "${detection.portal}" not in local cache. Run Sync first.`,
        });
        return;
      }
      // Resolve an active consent record. The backend requires one for
      // every submission — we never silently submit without consent.
      const consent = await getConsentForPortal(activeSupplier.id, portal.id);
      if (!consent) {
        setBanner({
          kind: "error",
          text: "No active consent for this supplier × portal. Capture blocked.",
        });
        return;
      }
      const resp = await send({
        type: "submission.capture",
        payload: {
          supplier_id: activeSupplier.id,
          portal_id: portal.id,
          consent_record_id: consent.id,
          payload: {
            captured_at: new Date().toISOString(),
            url: detection.url,
          },
        },
      });
      if (!resp.ok) {
        setBanner({ kind: "error", text: `Capture failed: ${resp.error}` });
        return;
      }
      setBanner({ kind: "success", text: `Captured submission ${resp.id.slice(0, 8)}.` });
    } finally {
      setCapturing(false);
    }
  };

  return (
    <section className="p-3 space-y-3" aria-labelledby="home-title">
      <h2 id="home-title" className="sr-only">Home</h2>

      <DetectedCard detection={detection} />

      <div>
        <label className="label" htmlFor="home-supplier">Supplier</label>
        <select
          id="home-supplier"
          className="input"
          value={active ?? ""}
          onChange={(e) => {
            if (tabId !== null) setActive(tabId, e.target.value);
          }}
          disabled={suppliers.length === 0}
        >
          {suppliers.length === 0 ? (
            <option value="">No suppliers — run Sync</option>
          ) : (
            suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.legal_name}
              </option>
            ))
          )}
        </select>
      </div>

      <button
        type="button"
        className="btn-primary w-full"
        onClick={() => void onFill()}
        disabled={filling || !detection || !activeSupplier}
      >
        {filling ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        ) : (
          <Send className="h-3.5 w-3.5" aria-hidden />
        )}
        Fill from supplier
      </button>

      <button
        type="button"
        className="btn-secondary w-full"
        onClick={() => void onCapture()}
        disabled={capturing || !detection || !activeSupplier}
      >
        {capturing ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        ) : (
          <Camera className="h-3.5 w-3.5" aria-hidden />
        )}
        Capture this submission
      </button>
    </section>
  );
}

function DetectedCard({ detection }: { detection: PortalDetection | null }): JSX.Element {
  if (!detection) {
    return (
      <div className="card p-3 text-xs text-slate-500 flex items-start gap-2">
        <ShieldAlert className="h-4 w-4 text-slate-400 mt-0.5 flex-shrink-0" aria-hidden />
        <div>
          <div className="font-medium text-slate-700">No portal detected</div>
          <div className="mt-0.5">
            Navigate to a supported carrier portal to enable filling.
          </div>
        </div>
      </div>
    );
  }
  const pct = Math.round(detection.confidence * 100);
  return (
    <div className="card p-3 text-xs">
      <div className="flex items-start gap-2">
        <CheckCircle2 className="h-4 w-4 text-emerald-600 mt-0.5 flex-shrink-0" aria-hidden />
        <div className="min-w-0">
          <div className="font-medium text-slate-800">
            Detected: <span className="font-mono">{detection.portal}</span>
          </div>
          <div className="text-[10px] text-slate-500 truncate" title={detection.url}>
            {detection.hostname}
          </div>
          <div
            className="mt-1 text-[10px] text-slate-500"
            data-testid="confidence"
          >
            confidence {pct}%
          </div>
        </div>
      </div>
    </div>
  );
}
