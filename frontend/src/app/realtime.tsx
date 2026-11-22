import { useQueryClient } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { qk } from '../api/hooks';
import { useSocketEvent } from '../api/socket';
import type { Finding, Thresholds } from '../api/types';

/** Subskrypcje socketu: odświeżanie cache po zmianie statusu rekordu i progów (np. w innej karcie). */
export function RealtimeProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();

  useSocketEvent('finding:updated', (f: Finding) => {
    qc.setQueryData(qk.finding(f.id), f);
    void qc.invalidateQueries({ queryKey: ['findings'] });
    void qc.invalidateQueries({ queryKey: ['overview'] });
  });

  useSocketEvent('thresholds:updated', (t: Thresholds) => {
    qc.setQueryData(qk.thresholds, t);
    for (const key of ['findings', 'finding', 'overview', 'timeseries', 'campaigns', 'campaign', 'graph', 'indicator', 'thresholdsPreview']) {
      void qc.invalidateQueries({ queryKey: [key] });
    }
  });

  return <>{children}</>;
}
