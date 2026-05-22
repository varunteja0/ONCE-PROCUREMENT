import { useCockpit } from '@/hooks/useCockpit';
import { useCockpitTenants } from '@/hooks/useCockpit';
import { Button } from '@/components/ui/Button';
import { X } from 'lucide-react';

export default function ActingAsBanner(): JSX.Element | null {
  const { actingAsTenantId, switchActAs } = useCockpit();
  const { data } = useCockpitTenants();

  if (!actingAsTenantId) return null;

  const tenant = data?.items.find((t) => t.id === actingAsTenantId);
  const label = tenant ? `${tenant.name} (${tenant.slug})` : actingAsTenantId;

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="acting-as-banner"
      className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-amber-300 bg-amber-100 px-4 py-2 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-900/40 dark:text-amber-100"
    >
      <span>
        <strong className="font-semibold">Acting as tenant:</strong> {label}
      </span>
      <Button
        size="sm"
        variant="ghost"
        onClick={() => {
          void switchActAs(null);
        }}
        aria-label="Exit tenant context"
      >
        <X className="mr-1 h-4 w-4" aria-hidden="true" />
        Exit tenant
      </Button>
    </div>
  );
}
