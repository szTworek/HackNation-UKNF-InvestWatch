import { Badge, Group, Tooltip } from '@mantine/core';
import type { CampaignStatus, ModuleId, RegisterStatus, RiskLevel, Status } from '../api/types';
import { fmtProb } from '../lib/format';
import {
  CAMPAIGN_STATUS_COLOR,
  CAMPAIGN_STATUS_LABEL,
  MODULE_LABEL,
  MODULE_SHORT,
  REGISTER_COLOR,
  REGISTER_LABEL,
  RISK_COLOR,
  RISK_LABEL,
  STATUS_COLOR,
  STATUS_LABEL,
} from '../lib/labels';

type Size = 'xs' | 'sm' | 'md' | 'lg';

export function RiskBadge({ level, size = 'sm' }: { level: RiskLevel; size?: Size }) {
  return (
    <Badge color={RISK_COLOR[level]} variant={level === 'CRITICAL' ? 'filled' : 'light'} size={size}>
      {RISK_LABEL[level]}
    </Badge>
  );
}

export function StatusBadge({ status, size = 'sm' }: { status: Status; size?: Size }) {
  return (
    <Badge color={STATUS_COLOR[status]} variant="outline" size={size}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}

export function ModuleBadges({ modules, size = 'sm' }: { modules: ModuleId[]; size?: Size }) {
  if (!modules.length) return null;
  return (
    <Group gap={4} wrap="nowrap">
      {modules.map((m) => (
        <Tooltip key={m} label={MODULE_LABEL[m]} withArrow>
          <Badge size={size} variant="default" radius="sm">
            {MODULE_SHORT[m]}
          </Badge>
        </Tooltip>
      ))}
    </Group>
  );
}

/** Scam p: wyróżniony, gdy przekracza próg. */
export function ScamBadge({ p, threshold, size = 'sm' }: { p: number; threshold: number; size?: Size }) {
  const hit = p >= threshold;
  return (
    <Tooltip label={hit ? `Podejrzenie oszustwa (próg ${fmtProb(threshold)})` : `Poniżej progu ${fmtProb(threshold)}`} withArrow>
      <Badge size={size} color={hit ? 'red' : 'gray'} variant={hit ? 'filled' : 'light'} radius="sm">
        {fmtProb(p)}
      </Badge>
    </Tooltip>
  );
}

export function RegisterBadge({ status, size = 'sm' }: { status: RegisterStatus; size?: Size }) {
  return (
    <Badge color={REGISTER_COLOR[status]} variant="light" size={size}>
      {REGISTER_LABEL[status]}
    </Badge>
  );
}

export function CampaignStatusBadge({ status, size = 'sm' }: { status: CampaignStatus; size?: Size }) {
  return (
    <Badge color={CAMPAIGN_STATUS_COLOR[status]} variant="light" size={size}>
      {CAMPAIGN_STATUS_LABEL[status]}
    </Badge>
  );
}
