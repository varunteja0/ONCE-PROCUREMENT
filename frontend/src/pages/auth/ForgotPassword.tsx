import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { forgotPasswordSchema, type ForgotPasswordFormValues } from "@/schemas/auth";
import { api } from "@/services/api";
import { zodResolver } from "@hookform/resolvers/zod";
import { Mail } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";

export default function ForgotPassword(): JSX.Element {
  const [submitted, setSubmitted] = useState(false);

  const form = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
    mode: "onBlur",
  });

  async function onSubmit(values: ForgotPasswordFormValues): Promise<void> {
    try {
      // BACKEND-COUPLED: depends on POST /auth/forgot-password being implemented.
      await api.post("/auth/forgot-password", values, { _onceSkipAuth: true });
    } catch {
      /* swallow — always show success to avoid account enumeration. */
    } finally {
      setSubmitted(true);
    }
  }

  const submitting = form.formState.isSubmitting;

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-6 flex items-center gap-2">
          <Mail className="h-6 w-6 text-slate-700 dark:text-slate-200" aria-hidden="true" />
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Forgot your password?</h1>
        </div>

        {submitted ? (
          <div
            role="status"
            className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200"
          >
            If an account exists for that email, we&apos;ve sent a reset link.
          </div>
        ) : (
          <>
            <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
              Enter your work email and we&apos;ll send you a password reset link.
            </p>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
              <Input
                label="Email"
                type="email"
                autoComplete="email"
                required
                disabled={submitting}
                {...form.register("email")}
                error={form.formState.errors.email?.message}
              />
              <Button type="submit" fullWidth loading={submitting} disabled={submitting}>
                {submitting ? "Sending…" : "Send reset link"}
              </Button>
            </form>
          </>
        )}

        <p className="mt-6 text-sm text-slate-600 dark:text-slate-400">
          Remembered it?{" "}
          <Link to="/login" className="font-medium text-slate-900 underline hover:no-underline dark:text-slate-200">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
