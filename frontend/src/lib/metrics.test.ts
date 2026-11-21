import { describe, expect, it } from 'vitest';
import type { EvalItem } from '../api/types';
import {
  averagePrecision,
  bestThreshold,
  confusionAt,
  f1,
  fBeta,
  metricsAt,
  prCurve,
  precision,
  presetThresholds,
  recall,
  seriesFor,
  thresholdSweep,
  type Label,
} from './metrics';

const scores = [0.95, 0.85, 0.7, 0.6, 0.4, 0.3, 0.2, 0.1];
const labels: Label[] = [1, 1, 0, 1, 0, 1, 0, 0];

describe('confusionAt', () => {
  it('liczy TP/FP/FN/TN dla progu (score >= próg = pozytyw)', () => {
    expect(confusionAt(scores, labels, 0.5)).toEqual({ tp: 3, fp: 1, fn: 1, tn: 3 });
  });

  it('próg równy score traktuje rekord jako pozytywny', () => {
    expect(confusionAt([0.5], [1], 0.5)).toEqual({ tp: 1, fp: 0, fn: 0, tn: 0 });
  });

  it('próg 0 oznacza wszystko jako pozytyw, próg > max nic', () => {
    expect(confusionAt(scores, labels, 0)).toEqual({ tp: 4, fp: 4, fn: 0, tn: 0 });
    expect(confusionAt(scores, labels, 0.99)).toEqual({ tp: 0, fp: 0, fn: 4, tn: 4 });
  });

  it('rzuca błąd przy różnej długości wejść', () => {
    expect(() => confusionAt([0.1, 0.2], [1], 0.5)).toThrow();
  });
});

describe('precision / recall / F-beta', () => {
  const c = { tp: 3, fp: 1, fn: 1, tn: 3 };

  it('liczy podstawowe metryki', () => {
    expect(precision(c)).toBeCloseTo(0.75);
    expect(recall(c)).toBeCloseTo(0.75);
    expect(f1(c)).toBeCloseTo(0.75);
  });

  it('F-beta waży pełność (β=2) albo precyzję (β=0.5)', () => {
    const highRecall = { tp: 4, fp: 4, fn: 0, tn: 0 }; // P=0.5, R=1
    expect(fBeta(highRecall, 2)).toBeCloseTo((5 * 0.5 * 1) / (4 * 0.5 + 1));
    expect(fBeta(highRecall, 2)).toBeGreaterThan(fBeta(highRecall, 0.5));
  });

  it('zwraca 0 zamiast NaN przy pustych mianownikach', () => {
    const none = { tp: 0, fp: 0, fn: 0, tn: 5 };
    expect(precision(none)).toBe(0);
    expect(recall(none)).toBe(0);
    expect(f1(none)).toBe(0);
  });

  it('odrzuca beta <= 0', () => {
    expect(() => fBeta(c, 0)).toThrow();
  });
});

describe('metricsAt', () => {
  it('łączy macierz pomyłek i metryki', () => {
    const m = metricsAt(scores, labels, 0.5);
    expect(m).toMatchObject({ tp: 3, fp: 1, fn: 1, tn: 3, threshold: 0.5 });
    expect(m.f1).toBeCloseTo(0.75);
  });

  it('podniesienie progu nie zwiększa FP i nie zmniejsza FN', () => {
    let prev = metricsAt(scores, labels, 0);
    for (let t = 0.05; t <= 1; t += 0.05) {
      const m = metricsAt(scores, labels, t);
      expect(m.fp).toBeLessThanOrEqual(prev.fp);
      expect(m.fn).toBeGreaterThanOrEqual(prev.fn);
      prev = m;
    }
  });
});

describe('prCurve', () => {
  it('zaczyna od (recall 0, precision 1) i kończy na recall 1', () => {
    const curve = prCurve(scores, labels);
    expect(curve[0]).toMatchObject({ recall: 0, precision: 1 });
    expect(curve[curve.length - 1].recall).toBe(1);
  });

  it('recall jest niemalejący, próg nierosnący', () => {
    const curve = prCurve(scores, labels);
    for (let i = 1; i < curve.length; i++) {
      expect(curve[i].recall).toBeGreaterThanOrEqual(curve[i - 1].recall);
      expect(curve[i].threshold).toBeLessThanOrEqual(curve[i - 1].threshold);
    }
  });

  it('łączy remisy score w jeden punkt', () => {
    const curve = prCurve([0.8, 0.8, 0.2], [1, 0, 1]);
    expect(curve).toHaveLength(3);
    expect(curve[1]).toMatchObject({ threshold: 0.8, precision: 0.5, recall: 0.5 });
  });

  it('punkt krzywej zgadza się z metricsAt dla tego samego progu', () => {
    for (const p of prCurve(scores, labels).slice(1)) {
      const m = metricsAt(scores, labels, p.threshold);
      expect(p.precision).toBeCloseTo(m.precision);
      expect(p.recall).toBeCloseTo(m.recall);
    }
  });
});

describe('averagePrecision', () => {
  it('daje 1 dla idealnego rankingu', () => {
    expect(averagePrecision([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0])).toBeCloseTo(1);
  });

  it('jest niższe dla gorszego rankingu', () => {
    expect(averagePrecision([0.9, 0.8, 0.2, 0.1], [0, 0, 1, 1])).toBeLessThan(0.6);
  });
});

describe('thresholdSweep', () => {
  it('zwraca steps+1 punktów od 0 do 1', () => {
    const sweep = thresholdSweep(scores, labels, 10);
    expect(sweep).toHaveLength(11);
    expect(sweep[0].threshold).toBe(0);
    expect(sweep[10].threshold).toBe(1);
    expect(sweep[0].recall).toBe(1);
  });
});

describe('bestThreshold', () => {
  it('dla separowalnych danych wybiera próg rozdzielający klasy', () => {
    const s = [0.9, 0.85, 0.8, 0.3, 0.2, 0.1];
    const l: Label[] = [1, 1, 1, 0, 0, 0];
    const best = bestThreshold(s, l, 1);
    expect(best.score).toBeCloseTo(1);
    expect(best.threshold).toBeGreaterThan(0.3);
    expect(best.threshold).toBeLessThanOrEqual(0.8);
  });

  it('β=2 daje próg nie wyższy niż β=0.5', () => {
    const hi = bestThreshold(scores, labels, 2).threshold;
    const lo = bestThreshold(scores, labels, 0.5).threshold;
    expect(hi).toBeLessThanOrEqual(lo);
  });
});

describe('seriesFor / presetThresholds', () => {
  const items: EvalItem[] = [
    { id: 'a', probs: { 'flags.X': 0.9, 'flags.Y': 0.1 }, gold: { 'flags.X': 1, 'flags.Y': 0 } },
    { id: 'b', probs: { 'flags.X': 0.2 }, gold: { 'flags.X': 0 } },
    { id: 'c', probs: { 'flags.X': 0.7, 'flags.Y': 0.8 }, gold: { 'flags.X': 1, 'flags.Y': 1 } },
  ];

  it('pomija rekordy bez danego klucza', () => {
    expect(seriesFor(items, 'flags.Y')).toEqual({ scores: [0.1, 0.8], labels: [0, 1] });
  });

  it('ustawia próg dla każdego klucza z pozytywami', () => {
    const preset = presetThresholds(items, ['flags.X', 'flags.Y', 'flags.Z'], 1);
    expect(Object.keys(preset).sort()).toEqual(['flags.X', 'flags.Y']);
    expect(preset['flags.X']).toBeGreaterThan(0.2);
    expect(preset['flags.X']).toBeLessThanOrEqual(0.7);
  });
});
