import { z } from 'zod';

const optional = z
  .string()
  .trim()
  .transform((v) => (v === '' ? null : v))
  .nullable()
  .optional();

const isoDate = z
  .string()
  .min(1, 'Date is required.')
  .refine((v) => !Number.isNaN(Date.parse(v)), 'Enter a valid date.');

export const coiSchema = z.object({
  supplier_id: z.string().min(1, 'Supplier is required.'),
  carrier: z.string().trim().min(1, 'Carrier is required.'),
  policy_number: optional,
  effective_date: optional,
  expires_at: isoDate,
  coverage_type: optional,
  limit_amount: optional,
  file_url: optional,
  notes: optional,
});
export type CoiFormValues = z.infer<typeof coiSchema>;

export const lossRunSchema = z
  .object({
    supplier_id: z.string().min(1, 'Supplier is required.'),
    period_start: isoDate,
    period_end: isoDate,
    carrier: optional,
    total_claims: z
      .union([z.string(), z.number()])
      .transform((v) => (v === '' || v === null || v === undefined ? null : Number(v)))
      .nullable()
      .refine(
        (v) => v === null || (Number.isFinite(v) && v >= 0),
        'Total claims must be a non-negative integer.',
      )
      .optional(),
    total_incurred: optional,
    file_url: optional,
    notes: optional,
  })
  .refine((v) => Date.parse(v.period_end) >= Date.parse(v.period_start), {
    message: 'Period end must be on or after period start.',
    path: ['period_end'],
  });
export type LossRunFormValues = z.infer<typeof lossRunSchema>;

export const producerLicenseSchema = z.object({
  supplier_id: z.string().min(1, 'Supplier is required.'),
  state: z
    .string()
    .trim()
    .length(2, 'Use the 2-letter state code (e.g. NY).')
    .transform((v) => v.toUpperCase()),
  license_number: z.string().trim().min(1, 'License number is required.'),
  license_type: optional,
  expires_at: isoDate,
  file_url: optional,
  notes: optional,
});
export type ProducerLicenseFormValues = z.infer<typeof producerLicenseSchema>;

export const eoCertificateSchema = z.object({
  supplier_id: z.string().min(1, 'Supplier is required.'),
  carrier: z.string().trim().min(1, 'Carrier is required.'),
  policy_number: optional,
  limit_amount: z.string().trim().min(1, 'Limit amount is required.'),
  retroactive_date: optional,
  expires_at: isoDate,
  file_url: optional,
  notes: optional,
});
export type EoCertificateFormValues = z.infer<typeof eoCertificateSchema>;

export const acordFormTypes = ['125', '126', '127', '128', '130', '140'] as const;

export const acordFormSchema = z.object({
  supplier_id: z.string().min(1, 'Supplier is required.'),
  form_type: z.enum(acordFormTypes),
  payload: z
    .string()
    .trim()
    .min(2, 'Payload JSON is required.')
    .refine((s) => {
      try {
        const v: unknown = JSON.parse(s);
        return typeof v === 'object' && v !== null;
      } catch {
        return false;
      }
    }, 'Payload must be valid JSON object.'),
  pdf_url: optional,
});
export type AcordFormValues = z.infer<typeof acordFormSchema>;

export const riskScheduleSchema = z.object({
  supplier_id: z.string().min(1, 'Supplier is required.'),
  line_of_business: z.string().trim().min(1, 'Line of business is required.'),
  payload: z
    .string()
    .trim()
    .min(2, 'Payload JSON is required.')
    .refine((s) => {
      try {
        const v: unknown = JSON.parse(s);
        return typeof v === 'object' && v !== null;
      } catch {
        return false;
      }
    }, 'Payload must be valid JSON object.'),
  effective_date: optional,
  notes: optional,
});
export type RiskScheduleFormValues = z.infer<typeof riskScheduleSchema>;
