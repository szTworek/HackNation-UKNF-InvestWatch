import { Box, Text } from '@mantine/core';
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';

/** Panel terminala: nagłówek z tytułem (bursztyn, mono) i treść. */
export function Panel({
  title,
  right,
  children,
  flush,
  style,
  delay = 0,
}: {
  title: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  flush?: boolean;
  style?: CSSProperties;
  /** opóźnienie animacji wejścia (ms), żeby panele wchodziły kaskadowo */
  delay?: number;
}) {
  return (
    <section className="iw-panel" style={{ animationDelay: `${delay}ms`, ...style }}>
      <div className="iw-panel-head">
        <span className="iw-panel-title">{title}</span>
        {right}
      </div>
      <div className={flush ? 'iw-panel-body flush' : 'iw-panel-body'}>{children}</div>
    </section>
  );
}

/** Liczba „dobiegająca” do nowej wartości i błyskająca przy zmianie. */
export function AnimatedNumber({ value, format = (n) => String(Math.round(n)), style }: { value: number; format?: (n: number) => string; style?: CSSProperties }) {
  const [shown, setShown] = useState(value);
  const [bump, setBump] = useState(0);
  const from = useRef(value);
  useEffect(() => {
    const start = performance.now();
    const a = from.current;
    const b = value;
    if (a === b) return;
    setBump((n) => n + 1);
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / 700);
      const eased = 1 - (1 - t) ** 3;
      setShown(a + (b - a) * eased);
      if (t < 1) raf = requestAnimationFrame(step);
      else from.current = b;
    };
    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf);
      from.current = b;
    };
  }, [value]);
  return (
    <span key={bump} className={bump ? 'iw-num iw-bump' : 'iw-num'} style={style}>
      {format(shown)}
    </span>
  );
}

/** Poziomy pasek wartości 0..1 z opcjonalną kreską progu. */
export function Meter({ value, color, threshold, h = 6 }: { value: number; color: string; threshold?: number; h?: number }) {
  return (
    <Box className="iw-meter" h={h}>
      <span style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, background: color }} />
      {threshold !== undefined && (
        <Box pos="absolute" top={0} bottom={0} w={2} bg="#1f2933" style={{ left: `calc(${threshold * 100}% - 1px)` }} />
      )}
    </Box>
  );
}

/** Etykieta + wartość w stylu terminala. */
export function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <Text size="xs" c="dimmed" fw={500}>
        {label}
      </Text>
      <Text size="sm" component="div">
        {children}
      </Text>
    </div>
  );
}

export const RISK_HEX = { LOW: '#8a939e', MEDIUM: '#d39e00', HIGH: '#e8590c', CRITICAL: '#c4314b' } as const;
