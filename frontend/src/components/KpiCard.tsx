import { Box, Paper, Skeleton, Text } from '@mantine/core';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface Props {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  to?: string;
  loading?: boolean;
  valueSize?: number;
  /** kolor akcentu z lewej (np. czerwony dla oszustw) */
  accent?: string;
}

export function KpiCard({ label, value, hint, to, loading, valueSize = 30, accent = 'var(--iw-primary)' }: Props) {
  const content = (
    <Box pl="sm" style={{ borderLeft: `3px solid ${accent}` }}>
      <Text size="sm" c="dimmed" fw={500}>
        {label}
      </Text>
      {loading ? (
        <Skeleton h={34} w={80} mt={6} />
      ) : (
        <Text fz={valueSize} fw={600} lh={1.25} mt={4} component="div" className="iw-kpi-value">
          {value}
        </Text>
      )}
      {hint && (
        <Text size="xs" c="dimmed" mt={2}>
          {hint}
        </Text>
      )}
    </Box>
  );
  if (to) {
    return (
      <Paper p="md" component={Link} to={to} style={{ color: 'inherit', textDecoration: 'none' }}>
        {content}
      </Paper>
    );
  }
  return <Paper p="md">{content}</Paper>;
}
