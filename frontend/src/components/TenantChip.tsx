import { Tooltip } from "@/components/ui";
import { cn } from "@/lib/cn";
import { Building2 } from "lucide-react";

export interface TenantChipProps {
  tenantId: string;
  className?: string;
}

// BACKEND-COUPLED: expects `GET /tenants/me` to return the tenant display name;
// until that endpoint exists we render the (truncated) tenant_id with the full
// id visible in the tooltip.
export function TenantChip({ tenantId, className }: TenantChipProps): JSX.Element {
  const short = tenantId.length > 8 ? `${tenantId.slice(0, 8)}…` : tenantId;
  return (
    <Tooltip label={`Tenant ${tenantId}`} className={className}>
      <span
        aria-label={`Current tenant ${tenantId}`}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700",
          "dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200",
        )}
      >
        <Building2 className="h-3.5 w-3.5 text-slate-500 dark:text-slate-400" aria-hidden="true" />
        <span className="font-mono">{short}</span>
      </span>
    </Tooltip>
  );
}

export default TenantChip;
