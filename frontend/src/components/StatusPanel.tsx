import { Anchor, Button, Group, Select, Stack, Text, Textarea, Timeline } from '@mantine/core';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { HistoryEntry, Revision, RiskLevel, Status } from '../api/types';
import { fmtDateTime } from '../lib/format';
import { RISK_LABEL, STATUSES, STATUS_LABEL } from '../lib/labels';

interface ChangerProps {
  status: Status;
  loading?: boolean;
  onSubmit: (status: Status, comment: string) => void;
}

export function StatusChanger({ status, loading, onSubmit }: ChangerProps) {
  const [next, setNext] = useState<Status>(status);
  const [comment, setComment] = useState('');
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(next, comment.trim());
        setComment('');
      }}
    >
      <Stack gap="xs">
        <Select
          label="Status"
          data={STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] }))}
          value={next}
          onChange={(v) => v && setNext(v as Status)}
          allowDeselect={false}
        />
        <Textarea label="Komentarz" autosize minRows={2} maxRows={5} value={comment} onChange={(e) => setComment(e.currentTarget.value)} />
        <Group justify="flex-end">
          <Button type="submit" loading={loading} disabled={next === status && !comment.trim()}>
            Zapisz status
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

/** Zmiany treści między wcześniejszą wersją a obecną: zdania dodane i usunięte. */
export function RevisionDiff({ revision, current }: { revision: Revision; current: RiskLevel }) {
  return (
    <Stack gap={6}>
      <Group gap="xs">
        <Text size="sm" fw={600}>
          Treść zmieniona po publikacji
        </Text>
        <Text size="xs" c="dimmed">
          wersja z {fmtDateTime(revision.fetchedAt)}
          {revision.riskLevel ? `: ryzyko ${RISK_LABEL[revision.riskLevel]} → ${RISK_LABEL[current]}` : ''}
        </Text>
      </Group>
      {revision.removed.map((s) => (
        <Text key={`r-${s}`} size="sm" px="xs" py={2} style={{ background: 'var(--mantine-color-red-0)', textDecoration: 'line-through' }}>
          − {s}
        </Text>
      ))}
      {revision.added.map((s) => (
        <Text key={`a-${s}`} size="sm" px="xs" py={2} style={{ background: 'var(--mantine-color-green-0)' }}>
          + {s}
        </Text>
      ))}
      {revision.findingId && (
        <Anchor component={Link} to={`/findings/${encodeURIComponent(revision.findingId)}`} size="xs">
          Otwórz poprzednią wersję
        </Anchor>
      )}
    </Stack>
  );
}

export function StatusHistory({ history }: { history: HistoryEntry[] }) {
  const items = [...history].reverse();
  return (
    <Timeline active={0} bulletSize={12} lineWidth={2}>
      {items.map((h, i) => (
        <Timeline.Item key={`${h.at}-${i}`} title={STATUS_LABEL[h.status]}>
          <Text size="xs" c="dimmed">
            {fmtDateTime(h.at)}, {h.user}
          </Text>
          {h.comment && <Text size="sm">{h.comment}</Text>}
        </Timeline.Item>
      ))}
    </Timeline>
  );
}
