import { createCrudClient } from '@/api/crud';
import type { RiskSchedule, RiskScheduleCreateInput } from '@/types/api';

export const riskSchedulesApi = createCrudClient<
  RiskSchedule,
  RiskScheduleCreateInput
>('risk-schedules');
