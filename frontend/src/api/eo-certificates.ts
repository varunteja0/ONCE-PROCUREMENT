import { createCrudClient } from '@/api/crud';
import type {
  EoCertificate,
  EoCertificateCreateInput,
} from '@/types/api';

export const eoCertificatesApi = createCrudClient<
  EoCertificate,
  EoCertificateCreateInput
>('eo-certificates');
