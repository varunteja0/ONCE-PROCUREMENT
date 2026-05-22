import { createCrudClient } from '@/api/crud';
import type {
  ProducerLicense,
  ProducerLicenseCreateInput,
} from '@/types/api';

export const producerLicensesApi = createCrudClient<
  ProducerLicense,
  ProducerLicenseCreateInput
>('producer-licenses');
