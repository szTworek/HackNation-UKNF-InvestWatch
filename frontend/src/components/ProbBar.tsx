import { Box, Group, Progress, Text, Tooltip, UnstyledButton } from '@mantine/core';
import { fmtProb } from '../lib/format';

interface Props {
  label: string;
  p: number;
  threshold?: number;
  color?: string;
  active?: boolean;
  onClick?: () => void;
  /** dopisek po prawej, np. liczba fragmentów */
  note?: string;
}

/** Pasek prawdopodobieństwa z kreską bieżącego progu. */
export function ProbBar({ label, p, threshold, color = 'blue', active, onClick, note }: Props) {
  const over = threshold === undefined || p >= threshold;
  const body = (
    <Box py={4} px={6} style={{ borderRadius: 4, background: active ? '#f1f3f6' : undefined }}>
      <Group justify="space-between" gap="xs" wrap="nowrap" mb={4}>
        <Text size="sm" fw={over && threshold !== undefined ? 500 : 400} c={over ? undefined : 'dimmed'} truncate>
          {label}
        </Text>
        <Group gap={6} wrap="nowrap">
          {note && (
            <Text size="xs" c="dimmed">
              {note}
            </Text>
          )}
          <Text size="sm">
            {fmtProb(p)}
          </Text>
        </Group>
      </Group>
      <Box pos="relative">
        <Progress value={p * 100} color={over ? color : 'gray.4'} size="sm" aria-label={`${label}: ${fmtProb(p)}`} />
        {threshold !== undefined && (
          <Tooltip label={`Próg ${fmtProb(threshold)}`} withArrow>
            <Box
              pos="absolute"
              top={-3}
              h={14}
              w={2}
              bg="#1f2933"
              style={{ left: `calc(${threshold * 100}% - 1px)` }}
            />
          </Tooltip>
        )}
      </Box>
    </Box>
  );
  if (!onClick) return body;
  return (
    <UnstyledButton onClick={onClick} w="100%" aria-pressed={active}>
      {body}
    </UnstyledButton>
  );
}
