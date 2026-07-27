import {
  _normalizeUnit,
  denormalizeMeasure,
  fmtMeasure,
  normalizeMeasure,
  normalizeUnit,
  toNum,
} from './measureUtils';

describe('measureUtils', () => {
  test('toNum parses Russian decimal comma and spaced thousands', () => {
    expect(toNum('0,027')).toBeCloseTo(0.027);
    expect(toNum('1 234,56')).toBeCloseTo(1234.56);
    expect(toNum('1\u00a0234,56')).toBeCloseTo(1234.56);
    expect(toNum(null)).toBe(0);
    expect(toNum(undefined)).toBe(0);
    expect(toNum('')).toBe(0);
    expect(toNum('не число')).toBe(0);
  });

  test('normalizeUnit collapses common estimate units', () => {
    expect(normalizeUnit('100 м2')).toBe('м2');
    expect(normalizeUnit('м²')).toBe('м2');
    expect(normalizeUnit('кв.м')).toBe('м2');
    expect(normalizeUnit('1000 шт')).toBe('шт');
    expect(normalizeUnit('пог.м')).toBe('м');
    expect(normalizeUnit('килограммов')).toBe('кг');
    expect(_normalizeUnit('м³')).toBe('м3');
  });

  test('normalizeMeasure expands prefixed estimate quantities', () => {
    expect(normalizeMeasure('0,23', '100 м2')).toEqual({ qty: 23, unit: 'м2', factor: 100 });
    expect(normalizeMeasure('0,5', '1000 шт')).toEqual({ qty: 500, unit: 'шт', factor: 1000 });
    expect(normalizeMeasure('7', 'шт')).toEqual({ qty: 7, unit: 'шт', factor: 1 });
  });

  test('denormalizeMeasure stores quantities back in imported units', () => {
    expect(denormalizeMeasure(23, '100 м2')).toBeCloseTo(0.23);
    expect(denormalizeMeasure(500, '1000 шт')).toBeCloseTo(0.5);
    expect(denormalizeMeasure(7, 'шт')).toBe(7);
  });

  test('fmtMeasure formats normalized quantities for Russian UI', () => {
    expect(fmtMeasure('0,23', '100 м2')).toBe('23 м2');
    expect(fmtMeasure('0,027', 'м3')).toBe('0,027 м3');
    expect(fmtMeasure('1,5', 'шт')).toBe('1,5 шт');
  });
});
