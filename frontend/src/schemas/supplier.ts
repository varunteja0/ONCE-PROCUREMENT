import { z } from 'zod';

const optionalTrimmed = z
  .string()
  .trim()
  .transform((v) => (v === '' ? null : v))
  .nullable()
  .optional();

export const supplierFormSchema = z.object({
  legal_name: z.string().trim().min(1, 'Legal name is required.'),
  dba_name: optionalTrimmed,
  ein: optionalTrimmed.refine(
    (v) => v === null || v === undefined || /^[0-9]{2}-?[0-9]{7}$/.test(v),
    { message: 'EIN must be 9 digits, optionally formatted as XX-XXXXXXX.' },
  ),
  naics_code: optionalTrimmed,
  primary_email: optionalTrimmed.refine(
    (v) =>
      v === null ||
      v === undefined ||
      z.string().email().safeParse(v).success,
    { message: 'Enter a valid email address.' },
  ),
  primary_phone: optionalTrimmed,
  website: optionalTrimmed.refine(
    (v) =>
      v === null ||
      v === undefined ||
      z.string().url().safeParse(v).success,
    { message: 'Enter a valid URL (e.g. https://example.com).' },
  ),
});
export type SupplierFormValues = z.infer<typeof supplierFormSchema>;
