import { z } from 'zod';

export const loginSchema = z.object({
  email: z.string().trim().email('Enter a valid email address.'),
  password: z.string().min(1, 'Password is required.'),
});
export type LoginFormValues = z.infer<typeof loginSchema>;

export const registerSchema = z.object({
  tenant_name: z.string().trim().min(2, 'Organization name is required.'),
  full_name: z.string().trim().min(1, 'Your full name is required.'),
  email: z.string().trim().email('Enter a valid email address.'),
  password: z
    .string()
    .min(8, 'Password must be at least 8 characters.')
    .max(256, 'Password is too long.'),
});
export type RegisterFormValues = z.infer<typeof registerSchema>;

export const passwordChangeSchema = z
  .object({
    current_password: z.string().min(1, 'Current password is required.'),
    new_password: z
      .string()
      .min(8, 'New password must be at least 8 characters.')
      .max(256),
    confirm_password: z.string().min(8),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    message: 'Passwords do not match.',
    path: ['confirm_password'],
  });
export type PasswordChangeFormValues = z.infer<typeof passwordChangeSchema>;

export const forgotPasswordSchema = z.object({
  email: z.string().trim().email('Enter a valid email address.'),
});
export type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

export const resetPasswordSchema = z
  .object({
    new_password: z
      .string()
      .min(8, 'New password must be at least 8 characters.')
      .max(256),
    confirm_password: z.string().min(8),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    message: 'Passwords do not match.',
    path: ['confirm_password'],
  });
export type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;
