import type {
  ApiHealth,
  BulkStatusUpdate,
  CampaignDetail,
  CampaignListItem,
  CampaignStatus,
  EvalItem,
  Finding,
  FindingSummary,
  FindingsQuery,
  Graph,
  HistoryRow,
  IndicatorFindings,
  IndicatorType,
  ModuleId,
  Page,
  RuleDef,
  StatsOverview,
  StatusUpdate,
  Thresholds,
  ThresholdsPreview,
  Timeseries,
  TimeseriesGroupBy,
} from './types';

export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:4000/api').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

type QueryValue = string | number | boolean | undefined | null | readonly (string | number)[];

/** Tablice jako `key[]=a&key[]=b` (kontrakt), boolean jako `1`, puste wartości pomijane. */
export function buildQuery(params: Record<string, QueryValue>): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '' || value === false) continue;
    if (Array.isArray(value)) {
      for (const v of value) sp.append(`${key}[]`, String(v));
    } else {
      sp.set(key, value === true ? '1' : String(value));
    }
  }
  const s = sp.toString();
  return s ? `?${s}` : '';
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    });
  } catch {
    throw new ApiError(0, 'Brak połączenia z API');
  }
  if (!res.ok) {
    let message = `Błąd API (${res.status})`;
    try {
      const body = (await res.json()) as { error?: string };
      if (body.error) message = body.error;
    } catch {
      // odpowiedź bez JSON
    }
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as T;
}

export interface DateRange {
  from?: string;
  to?: string;
}

export interface CampaignsQuery extends DateRange {
  minSize?: number;
  status?: CampaignStatus[];
  sort?: string;
}

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });

export const api = {
  health: () => request<ApiHealth>('/health'),
  findings: (q: FindingsQuery) => request<Page<FindingSummary>>(`/findings${buildQuery({ ...q })}`),
  finding: (id: string) => request<Finding>(`/findings/${encodeURIComponent(id)}`),
  updateStatus: (id: string, body: StatusUpdate) =>
    request<Finding>(`/findings/${encodeURIComponent(id)}/status`, { method: 'PATCH', ...json(body) }),
  bulkStatus: (body: BulkStatusUpdate) =>
    request<{ items: Finding[] }>('/findings/status', { method: 'PATCH', ...json(body) }),
  findingGraph: (id: string, depth: 1 | 2) => request<Graph>(`/findings/${encodeURIComponent(id)}/graph?depth=${depth}`),

  overview: (range: DateRange) => request<StatsOverview>(`/stats/overview${buildQuery({ ...range })}`),
  timeseries: (range: DateRange, groupBy: TimeseriesGroupBy) =>
    request<Timeseries>(`/stats/timeseries${buildQuery({ ...range, bucket: 'day', groupBy })}`),

  history: (q: DateRange & { user?: string; page?: number; pageSize?: number }) => request<Page<HistoryRow>>(`/history${buildQuery({ ...q })}`),
  rules: () => request<RuleDef[]>('/rules'),
  thresholds: () => request<Thresholds>('/thresholds'),
  saveThresholds: (values: Record<string, number>) => request<Thresholds>('/thresholds', { method: 'PUT', ...json({ values }) }),
  previewThresholds: (values: Record<string, number>) =>
    request<ThresholdsPreview>('/thresholds/preview', { method: 'POST', ...json({ values }) }),
  evalSet: () => request<EvalItem[]>('/calibration/eval-set'),

  campaigns: (q: CampaignsQuery) => request<Page<CampaignListItem>>(`/campaigns${buildQuery({ ...q })}`),
  campaign: (id: string) => request<CampaignDetail>(`/campaigns/${encodeURIComponent(id)}`),
  indicator: (type: IndicatorType, value: string) =>
    request<IndicatorFindings>(`/indicators/${type}/${encodeURIComponent(value)}`),

  reportUrl: (module: ModuleId, q: FindingsQuery) => {
    const rest: FindingsQuery = { ...q, module: undefined, page: undefined, pageSize: undefined };
    return `${API_URL}/reports/module/${module}.csv${buildQuery({ ...rest })}`;
  },
};
