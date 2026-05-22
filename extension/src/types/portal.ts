/**
 * Portal types — mirror of `backend/app/models/portal.py` and
 * `backend/app/schemas/portal.py`.
 *
 * Kept as plain string-literal unions so the values are stable, JSON-safe,
 * and trivially comparable with strings returned by the backend.
 */

export type PortalPlatform =
  | "applied_epic"
  | "vertafore_ams360"
  | "vertafore_sircon"
  | "amtrust"
  | "markel"
  | "nationwide_es"
  | "cna"
  | "guidewire"
  | "hawksoft"
  | "ezlynx"
  | "nowcerts";

export const PORTAL_PLATFORMS: readonly PortalPlatform[] = [
  "applied_epic",
  "vertafore_ams360",
  "vertafore_sircon",
  "amtrust",
  "markel",
  "nationwide_es",
  "cna",
  "guidewire",
  "hawksoft",
  "ezlynx",
  "nowcerts",
] as const;

export function isPortalPlatform(value: unknown): value is PortalPlatform {
  return (
    typeof value === "string" &&
    (PORTAL_PLATFORMS as readonly string[]).includes(value)
  );
}

/**
 * Read projection of a Portal row, mirroring `PortalRead` on the backend.
 */
export interface PortalDescriptor {
  id: string;
  platform: PortalPlatform;
  display_name: string;
  base_url: string | null;
  is_supported: boolean;
  risky: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PortalList {
  items: PortalDescriptor[];
  total: number;
}
