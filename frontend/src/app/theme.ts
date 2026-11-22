import { Badge, Button, Paper, Table, createTheme, type MantineColorsTuple } from '@mantine/core';

// granat z serwisu knf.gov.pl (#113B6F) jako odcień 7
const knf: MantineColorsTuple = [
  '#eef3f9',
  '#d8e3f0',
  '#b1c6e0',
  '#86a6cd',
  '#5f87b8',
  '#3f6ca1',
  '#255388',
  '#113b6f',
  '#0e315c',
  '#0a2848',
];

export const theme = createTheme({
  primaryColor: 'knf',
  primaryShade: 7,
  colors: { knf },
  black: '#2b303b',
  defaultRadius: 0,
  fontFamily: 'Inter, sans-serif',
  fontFamilyMonospace: 'Inter, sans-serif',
  headings: {
    fontFamily: 'Inter, sans-serif',
    fontWeight: '700',
    sizes: {
      h2: { fontSize: '2.25rem', lineHeight: '1.3' },
      h4: { fontSize: '1.125rem', lineHeight: '1.4' },
      h5: { fontSize: '1rem', lineHeight: '1.4' },
    },
  },
  components: {
    Paper: Paper.extend({ defaultProps: { withBorder: true, radius: 0 } }),
    Table: Table.extend({ classNames: { table: 'iw-table' } }),
    Button: Button.extend({ defaultProps: { radius: 0 } }),
    Badge: Badge.extend({ defaultProps: { radius: 2, tt: 'none' } }),
  },
});

/** Kolor modułu: paleta serwisu KNF, czerwień zarezerwowana dla podejrzeń oszustwa. */
export const MODULE_COLOR = {
  1: '#113b6f',
  2: '#1e6ac8',
  3: '#4b5f7c',
  scam: '#c00417',
  all: '#2b303b',
} as const;
