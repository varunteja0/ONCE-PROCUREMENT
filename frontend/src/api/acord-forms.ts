import { createCrudClient } from '@/api/crud';
import type { AcordForm, AcordFormCreateInput } from '@/types/api';

export const acordFormsApi = createCrudClient<AcordForm, AcordFormCreateInput>(
  'acord-forms',
);
