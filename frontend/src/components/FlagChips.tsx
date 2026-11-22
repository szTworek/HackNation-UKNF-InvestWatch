import { Badge, Group, Text, Tooltip } from '@mantine/core';
import type { FlagHit } from '../lib/findings';
import { fmtProb } from '../lib/format';
import { FLAG_COLOR, FLAG_LABEL } from '../lib/labels';

export function FlagChips({ flags, max = 3 }: { flags: FlagHit[]; max?: number }) {
  if (!flags.length) return <Text c="dimmed" size="xs">—</Text>;
  const shown = flags.slice(0, max);
  const rest = flags.length - shown.length;
  return (
    <Group gap={4}>
      {shown.map((f) => (
        <Tooltip key={f.flag} label={`p = ${fmtProb(f.p)}`} withArrow>
          <Badge size="xs" variant="light" color={FLAG_COLOR[f.flag]} radius="sm" tt="none">
            {FLAG_LABEL[f.flag]}
          </Badge>
        </Tooltip>
      ))}
      {rest > 0 && (
        <Tooltip label={flags.slice(max).map((f) => FLAG_LABEL[f.flag]).join(', ')} withArrow multiline w={240}>
          <Badge size="xs" variant="default" radius="sm">
            +{rest}
          </Badge>
        </Tooltip>
      )}
    </Group>
  );
}
