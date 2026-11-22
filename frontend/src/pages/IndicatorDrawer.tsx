import { Drawer, Text } from '@mantine/core';
import { useNavigate } from 'react-router-dom';
import { useIndicator, useThresholds } from '../api/hooks';
import type { Indicator } from '../api/types';
import { FindingList } from '../components/FindingsTable';
import { ErrorState, Loading } from '../components/PageState';
import { fmtInt } from '../lib/format';
import { INDICATOR_LABEL } from '../lib/labels';

/** Wszystkie rekordy z danym wskaźnikiem (telefon, domena, kanał…). */
export function IndicatorDrawer({ indicator, onClose }: { indicator: Indicator | null; onClose: () => void }) {
  const navigate = useNavigate();
  const thresholds = useThresholds();
  const q = useIndicator(indicator?.type, indicator?.value);
  return (
    <Drawer
      opened={!!indicator}
      onClose={onClose}
      position="right"
      size="xl"
      title={indicator ? `${INDICATOR_LABEL[indicator.type]}: ${indicator.value}` : ''}
    >
      {q.isError ? (
        <ErrorState error={q.error} />
      ) : !q.data ? (
        <Loading />
      ) : (
        <>
          <Text size="sm" c="dimmed" mb="sm">
            {fmtInt(q.data.findings.length)} rekordów
          </Text>
          <FindingList
            items={q.data.findings}
            onOpen={(id) => {
              onClose();
              navigate(`/findings/${id}`);
            }}
          />
        </>
      )}
    </Drawer>
  );
}
