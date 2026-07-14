import {
  calculatePublicProjectFinancing,
  serializePublicProjectFinancing,
} from './publicProjectFinancing';

describe('public project financing', () => {
  test('calculates an indicative mortgage range with an annuity payment', () => {
    const result = calculatePublicProjectFinancing({
      mode: 'mortgage',
      estimateMin: 10_000_000,
      estimateMax: 12_000_000,
      downPaymentPercent: 20,
      term: 20,
      annualRate: 12,
    });

    expect(result.mode).toBe('mortgage');
    expect(result.financedMin).toBe(8_000_000);
    expect(result.financedMax).toBe(9_600_000);
    expect(result.monthlyMin).toBeGreaterThan(80_000);
    expect(result.monthlyMax).toBeGreaterThan(result.monthlyMin);
    expect(result.termLabel).toBe('20 лет');
  });

  test('calculates installment payments without presenting them as a bank offer', () => {
    const result = calculatePublicProjectFinancing({
      mode: 'installment',
      estimateMin: 10_000_000,
      estimateMax: 12_000_000,
      downPaymentPercent: 30,
      term: 12,
    });

    expect(result.monthlyMin).toBe(583_333);
    expect(result.monthlyMax).toBe(700_000);
    expect(result.termLabel).toBe('12 месяцев');
    expect(result.annualRate).toBeNull();
  });

  test('serializes only the customer-selected indicative scenario for CRM', () => {
    const result = calculatePublicProjectFinancing({
      mode: 'mortgage',
      estimateMin: 10_000_000,
      estimateMax: 12_000_000,
      downPaymentPercent: 20,
      term: 20,
      annualRate: 12,
    });

    expect(serializePublicProjectFinancing(result)).toEqual(expect.objectContaining({
      status: 'indicative',
      mode: 'mortgage',
      modeLabel: 'Ипотека на строительство',
      downPaymentPercent: 20,
      termLabel: '20 лет',
      annualRate: 12,
    }));
  });
});
