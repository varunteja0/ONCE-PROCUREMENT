import { createCrudClient } from '@/api/crud';
import type { Coi, CoiCreateInput } from '@/types/api';

export const coisApi = createCrudClient<Coi, CoiCreateInput>('cois');
