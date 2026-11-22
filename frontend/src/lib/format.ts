import dayjs from 'dayjs';
import 'dayjs/locale/pl';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(relativeTime);
dayjs.locale('pl');

const pct0 = new Intl.NumberFormat('pl-PL', { style: 'percent', maximumFractionDigits: 0 });
const pct1 = new Intl.NumberFormat('pl-PL', { style: 'percent', maximumFractionDigits: 1 });
const dec2 = new Intl.NumberFormat('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const int = new Intl.NumberFormat('pl-PL');
const compact = new Intl.NumberFormat('pl-PL', { notation: 'compact', maximumFractionDigits: 1 });

export const fmtDateTime = (iso?: string) => (iso ? dayjs(iso).format('DD.MM.YYYY HH:mm') : '—');
export const fmtDate = (iso?: string) => (iso ? dayjs(iso).format('DD.MM.YYYY') : '—');
export const fmtTime = (iso: string) => dayjs(iso).format('HH:mm:ss');
export const fmtShortDate = (iso: string) => dayjs(iso).format('DD.MM');
export const fmtRelative = (iso: string) => dayjs(iso).fromNow();
export const fmtPct = (x: number, digits: 0 | 1 = 0) => (digits ? pct1 : pct0).format(x);
/** Prawdopodobieństwo / próg: 0,87 */
export const fmtProb = (p: number) => dec2.format(p);
export const fmtInt = (n: number) => int.format(n);
export const fmtCompact = (n: number) => compact.format(n);

export const todayIso = () => dayjs().format('YYYY-MM-DD');
export const daysAgoIso = (n: number) => dayjs().subtract(n, 'day').format('YYYY-MM-DD');
