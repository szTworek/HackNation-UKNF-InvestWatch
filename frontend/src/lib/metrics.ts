// Metryki panelu kalibracji. Czyste funkcje, bez zależności od Reacta.
// Konwencja: rekord jest pozytywny, gdy score >= próg.

import type { EvalItem } from '../api/types';

export type Label = 0 | 1;

export interface Confusion {
  tp: number;
  fp: number;
  fn: number;
  tn: number;
}

export interface Metrics extends Confusion {
  threshold: number;
  precision: number;
  recall: number;
  f1: number;
}

export interface PrPoint {
  threshold: number;
  precision: number;
  recall: number;
}

export interface SweepPoint {
  threshold: number;
  precision: number;
  recall: number;
  f1: number;
}

export interface Series {
  scores: number[];
  labels: Label[];
}

function assertSameLength(scores: readonly number[], labels: readonly Label[]): void {
  if (scores.length !== labels.length) {
    throw new Error(`scores (${scores.length}) i labels (${labels.length}) mają różną długość`);
  }
}

export function confusionAt(scores: readonly number[], labels: readonly Label[], threshold: number): Confusion {
  assertSameLength(scores, labels);
  let tp = 0;
  let fp = 0;
  let fn = 0;
  let tn = 0;
  for (let i = 0; i < scores.length; i++) {
    const predicted = scores[i] >= threshold;
    if (labels[i] === 1) {
      if (predicted) tp++;
      else fn++;
    } else if (predicted) fp++;
    else tn++;
  }
  return { tp, fp, fn, tn };
}

/** Precyzja; 0, gdy nic nie zostało oznaczone jako pozytywne. */
export function precision(c: Confusion): number {
  const d = c.tp + c.fp;
  return d === 0 ? 0 : c.tp / d;
}

/** Pełność (recall); 0, gdy w zbiorze nie ma pozytywów. */
export function recall(c: Confusion): number {
  const d = c.tp + c.fn;
  return d === 0 ? 0 : c.tp / d;
}

export function fBeta(c: Confusion, beta: number): number {
  if (beta <= 0) throw new Error('beta musi być > 0');
  const p = precision(c);
  const r = recall(c);
  const b2 = beta * beta;
  const d = b2 * p + r;
  return d === 0 ? 0 : ((1 + b2) * p * r) / d;
}

export function f1(c: Confusion): number {
  return fBeta(c, 1);
}

export function metricsAt(scores: readonly number[], labels: readonly Label[], threshold: number): Metrics {
  const c = confusionAt(scores, labels, threshold);
  return { ...c, threshold, precision: precision(c), recall: recall(c), f1: f1(c) };
}

/**
 * Krzywa precision–recall. Jeden punkt na każdą unikalną wartość score (jako próg),
 * plus punkt startowy (recall 0, precision 1). Wynik posortowany rosnąco po recall.
 */
export function prCurve(scores: readonly number[], labels: readonly Label[]): PrPoint[] {
  assertSameLength(scores, labels);
  const positives = labels.reduce<number>((s, l) => s + l, 0);
  const order = scores.map((_, i) => i).sort((a, b) => scores[b] - scores[a]);
  const points: PrPoint[] = [];
  const top = order.length ? scores[order[0]] : 1;
  points.push({ threshold: Math.min(1, top + 1e-9), precision: 1, recall: 0 });
  let tp = 0;
  let fp = 0;
  for (let k = 0; k < order.length; k++) {
    const i = order[k];
    if (labels[i] === 1) tp++;
    else fp++;
    const next = order[k + 1];
    // punkt dopiero po zebraniu wszystkich rekordów z tym samym score
    if (next !== undefined && scores[next] === scores[i]) continue;
    points.push({
      threshold: scores[i],
      precision: tp / (tp + fp),
      recall: positives === 0 ? 0 : tp / positives,
    });
  }
  return points;
}

/** Pole pod krzywą PR liczone jak average precision (suma Δrecall × precision). */
export function averagePrecision(scores: readonly number[], labels: readonly Label[]): number {
  const curve = prCurve(scores, labels);
  let ap = 0;
  for (let k = 1; k < curve.length; k++) {
    ap += (curve[k].recall - curve[k - 1].recall) * curve[k].precision;
  }
  return ap;
}

/** Precyzja, pełność i F1 dla progów 0, 1/steps, …, 1. */
export function thresholdSweep(scores: readonly number[], labels: readonly Label[], steps = 100): SweepPoint[] {
  const out: SweepPoint[] = [];
  for (let s = 0; s <= steps; s++) {
    const t = round2(s / steps);
    const m = metricsAt(scores, labels, t);
    out.push({ threshold: t, precision: m.precision, recall: m.recall, f1: m.f1 });
  }
  return out;
}

/**
 * Próg maksymalizujący F-beta na siatce 0.01–0.99.
 * Przy remisie wybiera środek najszerszego zakresu progów z tym samym wynikiem.
 */
export function bestThreshold(
  scores: readonly number[],
  labels: readonly Label[],
  beta: number,
): { threshold: number; score: number } {
  const grid: number[] = [];
  for (let s = 1; s <= 99; s++) grid.push(round2(s / 100));
  const values = grid.map((t) => fBeta(confusionAt(scores, labels, t), beta));
  const max = Math.max(...values);
  const eps = 1e-12;
  // najdłuższy ciągły odcinek z wartością max
  let bestStart = 0;
  let bestLen = 0;
  let start = -1;
  for (let i = 0; i <= values.length; i++) {
    const isMax = i < values.length && Math.abs(values[i] - max) <= eps;
    if (isMax && start < 0) start = i;
    if (!isMax && start >= 0) {
      const len = i - start;
      if (len > bestLen) {
        bestLen = len;
        bestStart = start;
      }
      start = -1;
    }
  }
  const mid = bestStart + Math.floor((bestLen - 1) / 2);
  return { threshold: grid[mid], score: max };
}

/** Wyciąga z eval-setu wyniki i etykiety dla jednego klucza progu. */
export function seriesFor(items: readonly EvalItem[], key: string): Series {
  const scores: number[] = [];
  const labels: Label[] = [];
  for (const item of items) {
    const p = item.probs[key];
    const g = item.gold[key];
    if (p === undefined || g === undefined) continue;
    scores.push(p);
    labels.push(g);
  }
  return { scores, labels };
}

/** Progi dla wszystkich kluczy, wybrane wg F-beta (preset kalibracji). */
export function presetThresholds(items: readonly EvalItem[], keys: readonly string[], beta: number): Record<string, number> {
  const out: Record<string, number> = {};
  for (const key of keys) {
    const { scores, labels } = seriesFor(items, key);
    if (scores.length === 0 || !labels.includes(1)) continue;
    out[key] = bestThreshold(scores, labels, beta).threshold;
  }
  return out;
}

export function round2(x: number): number {
  return Math.round(x * 100) / 100;
}
