import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { FindingsQuery, FlagKey, ModuleId, Platform, RiskLevel, Status } from '../api/types';
import { daysAgoIso, todayIso } from './format';
import { ALL_FLAGS, MODULES, PLATFORMS, RISK_LEVELS, STATUSES } from './labels';

export const DEFAULT_RANGE_DAYS = 30;
const RANGE_KEYS = ['from', 'to'] as const;

/** Globalny zakres dat (header), trzymany w URL i wspólny dla ekranów. */
export function useDateRange() {
  const [params, setParams] = useSearchParams();
  const from = params.get('from') ?? daysAgoIso(DEFAULT_RANGE_DAYS - 1);
  const to = params.get('to') ?? todayIso();
  const setRange = useCallback(
    (nextFrom: string, nextTo: string) => {
      setParams(
        (prev) => {
          const p = new URLSearchParams(prev);
          p.set('from', nextFrom);
          p.set('to', nextTo);
          p.delete('page');
          return p;
        },
        { replace: true },
      );
    },
    [setParams],
  );
  return useMemo(() => ({ from, to, setRange }), [from, to, setRange]);
}

/** `?from=…&to=…` do linków nawigacji, żeby zakres dat szedł za użytkownikiem. */
export function useRangeSearch(): string {
  const [params] = useSearchParams();
  const p = new URLSearchParams();
  for (const k of RANGE_KEYS) {
    const v = params.get(k);
    if (v) p.set(k, v);
  }
  const s = p.toString();
  return s ? `?${s}` : '';
}

function list<T extends string | number>(params: URLSearchParams, key: string, allowed: readonly T[]): T[] {
  return params
    .getAll(key)
    .flatMap((v) => v.split(','))
    .map((v) => (typeof allowed[0] === 'number' ? Number(v) : v) as T)
    .filter((v) => allowed.includes(v));
}

export interface FindingsFilters {
  q: string;
  platform: Platform[];
  module: ModuleId[];
  riskLevel: RiskLevel[];
  status: Status[];
  flag: FlagKey[];
  sort: string;
  page: number;
  pageSize: number;
}

export const DEFAULT_SORT = 'fetchedAt:desc';
export const PAGE_SIZES = [25, 50, 100];

export function parseFindingsFilters(params: URLSearchParams): FindingsFilters {
  const pageSize = Number(params.get('pageSize'));
  return {
    q: params.get('q') ?? '',
    platform: list(params, 'platform', PLATFORMS),
    module: list(params, 'module', MODULES),
    riskLevel: list(params, 'riskLevel', RISK_LEVELS),
    status: list(params, 'status', STATUSES),
    flag: list(params, 'flag', ALL_FLAGS),
    sort: params.get('sort') ?? DEFAULT_SORT,
    page: Math.max(1, Number(params.get('page')) || 1),
    pageSize: PAGE_SIZES.includes(pageSize) ? pageSize : 25,
  };
}

/** Filtry tabeli wyników w query stringu (link da się wysłać). */
export function useFindingsFilters() {
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => parseFindingsFilters(params), [params]);

  const update = useCallback(
    (patch: Partial<FindingsFilters>) => {
      setParams(
        (prev) => {
          const p = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(patch)) {
            p.delete(key);
            if (Array.isArray(value)) value.forEach((v) => p.append(key, String(v)));
            else if (value !== '' && value !== undefined && value !== null) p.set(key, String(value));
          }
          if (!('page' in patch)) p.delete('page');
          if (p.get('sort') === DEFAULT_SORT) p.delete('sort');
          if (p.get('page') === '1') p.delete('page');
          if (p.get('pageSize') === '25') p.delete('pageSize');
          return p;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  const reset = useCallback(() => {
    setParams(
      (prev) => {
        const p = new URLSearchParams();
        for (const k of RANGE_KEYS) {
          const v = prev.get(k);
          if (v) p.set(k, v);
        }
        return p;
      },
      { replace: true },
    );
  }, [setParams]);

  return { filters, update, reset };
}

export function toFindingsQuery(f: FindingsFilters, range: { from: string; to: string }): FindingsQuery {
  return {
    from: range.from,
    to: range.to,
    q: f.q || undefined,
    platform: f.platform,
    module: f.module,
    riskLevel: f.riskLevel,
    status: f.status,
    flag: f.flag,
    sort: f.sort,
    page: f.page,
    pageSize: f.pageSize,
  };
}

/** Link do listy wyników z gotowymi filtrami (np. z kafelka KPI). */
export function findingsLink(rangeSearch: string, extra: Record<string, string | string[]>): string {
  const p = new URLSearchParams(rangeSearch.replace(/^\?/, ''));
  for (const [k, v] of Object.entries(extra)) {
    if (Array.isArray(v)) v.forEach((x) => p.append(k, x));
    else p.set(k, v);
  }
  const s = p.toString();
  return `/findings${s ? `?${s}` : ''}`;
}
