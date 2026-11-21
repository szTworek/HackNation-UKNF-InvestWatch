import { Paper, Table, createTheme, type MantineColorsTuple } from '@mantine/core';

// biurowy błękit (jak w aplikacjach pakietu biurowego), od jasnego do ciemnego
const office: MantineColorsTuple = [
  '#ebf3fc',
  '#d4e4f7',
  '#a9c9ef',
  '#7aabe6',
  '#5392de',
  '#3a82d9',
  '#2477d3',
  '#0f6cbd',
  '#0c5aa0',
  '#094a85',
];

export const theme = createTheme({
  primaryColor: 'office',
  primaryShade: 7,
  colors: { office },
  defaultRadius: 'md',
  fontFamily: '"IBM Plex Sans", "Segoe UI", system-ui, sans-serif',
  fontFamilyMonospace: '"IBM Plex Mono", ui-monospace, monospace',
  headings: { fontFamily: '"IBM Plex Sans", "Segoe UI", system-ui, sans-serif', fontWeight: '600' },
  components: {
    Paper: Paper.extend({ defaultProps: { withBorder: true, radius: 'md' } }),
    Table: Table.extend({ classNames: { table: 'iw-table' } }),
  },
});

/** Kolor każdego modułu i ścieżki oszustw – ten sam w nawigacji, nagłówkach i plakietkach. */
export const MODULE_COLOR = {
  1: '#0f6cbd',
  2: '#0e7a5f',
  3: '#7a3fb0',
  scam: '#c4314b',
  all: '#4b5563',
} as const;
