import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useIdleTimer } from "@/lib/idle";
import { toast } from "@/lib/toast";
import { tokenStorage } from "@/services/api";
import { useAuthStore } from "@/store/auth";
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

const IDLE_MS = 15 * 60 * 1000;
const WARNING_MS = 60 * 1000;

/**
 * Warns the user 60 seconds before idle logout, then signs them out at
 * `IDLE_MS` of inactivity. Mount once inside the authenticated layout.
 */
export function IdleGuard(): JSX.Element | null {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const clearSession = useAuthStore((s) => s.clearSession);
  const navigate = useNavigate();
  const [warning, setWarning] = useState(false);

  const signOut = useCallback((): void => {
    setWarning(false);
    tokenStorage.clear();
    clearSession();
    toast.info("You were signed out due to inactivity.");
    navigate("/login", { replace: true });
  }, [clearSession, navigate]);

  const { reset } = useIdleTimer({
    idleMs: IDLE_MS,
    warningMs: WARNING_MS,
    enabled: isAuthenticated,
    onWarn: () => setWarning(true),
    onIdle: signOut,
  });

  const stay = useCallback((): void => {
    setWarning(false);
    reset();
  }, [reset]);

  if (!isAuthenticated) return null;

  return (
    <Modal
      open={warning}
      onClose={stay}
      title="Still there?"
      description="You'll be signed out in 60 seconds for inactivity."
      size="sm"
      closeOnBackdrop={false}
      footer={
        <>
          <Button variant="ghost" onClick={signOut}>
            Sign out now
          </Button>
          <Button onClick={stay}>Stay signed in</Button>
        </>
      }
    >
      <p className="text-sm text-slate-600 dark:text-slate-300">
        For your security, Once signs you out after a period of inactivity. Click{" "}
        <span className="font-medium">Stay signed in</span> to continue your session.
      </p>
    </Modal>
  );
}
