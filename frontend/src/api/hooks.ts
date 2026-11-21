import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type CampaignsQuery, type DateRange } from './client';
import type { BulkStatusUpdate, Finding, FindingsQuery, IndicatorType, Status, TimeseriesGroupBy } from './types';

export const qk = {
  findings: (q: FindingsQuery) => ['findings', q] as const,
  finding: (id: string) => ['finding', id] as const,
  graph: (id: string, depth: 1 | 2) => ['graph', id, depth] as const,
  overview: (r: DateRange) => ['overview', r] as const,
  timeseries: (r: DateRange, g: TimeseriesGroupBy) => ['timeseries', r, g] as const,
  rules: ['rules'] as const,
  thresholds: ['thresholds'] as const,
  preview: (v: Record<string, number>) => ['thresholdsPreview', v] as const,
  evalSet: ['evalSet'] as const,
  campaigns: (q: CampaignsQuery) => ['campaigns', q] as const,
  campaign: (id: string) => ['campaign', id] as const,
  indicator: (t: IndicatorType, v: string) => ['indicator', t, v] as const,
};

export function useFindings(q: FindingsQuery) {
  return useQuery({ queryKey: qk.findings(q), queryFn: () => api.findings(q), placeholderData: keepPreviousData });
}

export function useFinding(id: string | undefined) {
  return useQuery({ queryKey: qk.finding(id ?? ''), queryFn: () => api.finding(id ?? ''), enabled: !!id });
}

export function useFindingGraph(id: string | undefined, depth: 1 | 2) {
  return useQuery({
    queryKey: qk.graph(id ?? '', depth),
    queryFn: () => api.findingGraph(id ?? '', depth),
    enabled: !!id,
    placeholderData: keepPreviousData,
  });
}

export function useOverview(range: DateRange) {
  return useQuery({ queryKey: qk.overview(range), queryFn: () => api.overview(range), placeholderData: keepPreviousData });
}

export function useTimeseries(range: DateRange, groupBy: TimeseriesGroupBy) {
  return useQuery({
    queryKey: qk.timeseries(range, groupBy),
    queryFn: () => api.timeseries(range, groupBy),
    placeholderData: keepPreviousData,
  });
}

export function useHistory(q: DateRange & { user?: string; page?: number; pageSize?: number }) {
  return useQuery({ queryKey: ['history', q], queryFn: () => api.history(q), placeholderData: keepPreviousData });
}

export function useRules() {
  return useQuery({ queryKey: qk.rules, queryFn: api.rules, staleTime: Infinity });
}

export function useThresholds() {
  return useQuery({ queryKey: qk.thresholds, queryFn: api.thresholds, staleTime: 5 * 60_000 });
}

export function useThresholdsPreview(values: Record<string, number> | null) {
  return useQuery({
    queryKey: qk.preview(values ?? {}),
    queryFn: () => api.previewThresholds(values ?? {}),
    enabled: values !== null,
    placeholderData: keepPreviousData,
  });
}

export function useEvalSet() {
  return useQuery({ queryKey: qk.evalSet, queryFn: api.evalSet, staleTime: Infinity });
}

export function useCampaigns(q: CampaignsQuery) {
  return useQuery({ queryKey: qk.campaigns(q), queryFn: () => api.campaigns(q), placeholderData: keepPreviousData });
}

export function useCampaign(id: string | undefined) {
  return useQuery({ queryKey: qk.campaign(id ?? ''), queryFn: () => api.campaign(id ?? ''), enabled: !!id });
}

export function useIndicator(type: IndicatorType | undefined, value: string | undefined) {
  return useQuery({
    queryKey: qk.indicator(type ?? 'domain', value ?? ''),
    queryFn: () => api.indicator(type ?? 'domain', value ?? ''),
    enabled: !!type && !!value,
  });
}

/** Po zmianie statusu odświeżamy listy, statystyki i kampanie; sam rekord podmieniamy w cache. */
function useInvalidateAfterStatus() {
  const qc = useQueryClient();
  return (updated: Finding[]) => {
    for (const f of updated) qc.setQueryData(qk.finding(f.id), f);
    void qc.invalidateQueries({ queryKey: ['findings'] });
    void qc.invalidateQueries({ queryKey: ['overview'] });
    void qc.invalidateQueries({ queryKey: ['campaigns'] });
    void qc.invalidateQueries({ queryKey: ['campaign'] });
    void qc.invalidateQueries({ queryKey: ['indicator'] });
    void qc.invalidateQueries({ queryKey: ['history'] });
  };
}

export function useUpdateStatus() {
  const after = useInvalidateAfterStatus();
  return useMutation({
    mutationFn: ({ id, status, comment }: { id: string; status: Status; comment?: string }) =>
      api.updateStatus(id, { status, comment }),
    onSuccess: (f) => after([f]),
  });
}

export function useBulkStatus() {
  const after = useInvalidateAfterStatus();
  return useMutation({
    mutationFn: (body: BulkStatusUpdate) => api.bulkStatus(body),
    onSuccess: (res) => after(res.items),
  });
}

export function useSaveThresholds() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (values: Record<string, number>) => api.saveThresholds(values),
    onSuccess: (t) => {
      qc.setQueryData(qk.thresholds, t);
      void qc.invalidateQueries({ queryKey: ['thresholdsPreview'] });
    },
  });
}
