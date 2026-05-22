import { buildCrudHooks } from '@/hooks/useCrud';
import { coisApi } from '@/api/cois';
import { lossRunsApi } from '@/api/loss-runs';
import { producerLicensesApi } from '@/api/producer-licenses';
import { eoCertificatesApi } from '@/api/eo-certificates';
import { acordFormsApi } from '@/api/acord-forms';
import { riskSchedulesApi } from '@/api/risk-schedules';
import type {
  AcordForm,
  AcordFormCreateInput,
  Coi,
  CoiCreateInput,
  EoCertificate,
  EoCertificateCreateInput,
  LossRun,
  LossRunCreateInput,
  ProducerLicense,
  ProducerLicenseCreateInput,
  RiskSchedule,
  RiskScheduleCreateInput,
} from '@/types/api';

export const coisHooks = buildCrudHooks<Coi, CoiCreateInput>(coisApi, 'cois');
export const lossRunsHooks = buildCrudHooks<LossRun, LossRunCreateInput>(
  lossRunsApi,
  'loss-runs',
);
export const producerLicensesHooks = buildCrudHooks<
  ProducerLicense,
  ProducerLicenseCreateInput
>(producerLicensesApi, 'producer-licenses');
export const eoCertificatesHooks = buildCrudHooks<
  EoCertificate,
  EoCertificateCreateInput
>(eoCertificatesApi, 'eo-certificates');
export const acordFormsHooks = buildCrudHooks<AcordForm, AcordFormCreateInput>(
  acordFormsApi,
  'acord-forms',
);
export const riskSchedulesHooks = buildCrudHooks<
  RiskSchedule,
  RiskScheduleCreateInput
>(riskSchedulesApi, 'risk-schedules');
