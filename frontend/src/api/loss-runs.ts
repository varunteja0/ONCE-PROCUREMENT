import { createCrudClient } from '@/api/crud';
import type { LossRun, LossRunCreateInput } from '@/types/api';

export const lossRunsApi = createCrudClient<LossRun, LossRunCreateInput>('loss-runs');
