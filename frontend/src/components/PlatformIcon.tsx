import { Tooltip } from '@mantine/core';
import {
  IconBrandFacebook,
  IconBrandInstagram,
  IconBrandTiktok,
  IconBrandX,
  IconBrandYoutube,
  IconQuestionMark,
  IconWorldWww,
  type Icon,
} from '@tabler/icons-react';
import type { Platform } from '../api/types';
import { PLATFORM_LABEL } from '../lib/labels';

const ICONS: Record<Platform, Icon> = {
  facebook: IconBrandFacebook,
  instagram: IconBrandInstagram,
  tiktok: IconBrandTiktok,
  youtube: IconBrandYoutube,
  x: IconBrandX,
  web: IconWorldWww,
  other: IconQuestionMark,
};

export function PlatformIcon({ platform, size = 18, color = 'var(--mantine-color-gray-7)' }: { platform: Platform; size?: number; color?: string }) {
  const I = ICONS[platform];
  return (
    <Tooltip label={PLATFORM_LABEL[platform]} withArrow>
      <span style={{ display: 'inline-flex', color }}>
        <I size={size} stroke={1.6} aria-label={PLATFORM_LABEL[platform]} role="img" />
      </span>
    </Tooltip>
  );
}
