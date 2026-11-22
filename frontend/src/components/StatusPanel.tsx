import { Button, Group, Select, Stack, Text, Textarea, Timeline } from '@mantine/core';
import { useState } from 'react';
import type { HistoryEntry, Status } from '../api/types';
import { fmtDateTime } from '../lib/format';
import { STATUSES, STATUS_LABEL } from '../lib/labels';

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
