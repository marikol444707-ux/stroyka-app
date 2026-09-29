import { buildCustomerActPreview } from './actPreview';

test.each(['ks2', 'ks3'])('the %s preview preserves cents and escapes all displayed terms', kind => {
  const result = buildCustomerActPreview({ name: '<script>bad()</script>' }, {
    sourceItems: [{ description: '<img src=x onerror=bad()>', unit: '<svg>', quantity: 1, pricePerUnit: 10.25, total: 10.25 }],
    additionalVolumeItems: [], outsideEstimateItems: [{ description: 'Extra', quantity: 1, pricePerUnit: 3.12, total: 3.12 }],
  }, kind);
  expect(result).toContain('13,37');
  expect(result).toContain('&lt;script&gt;');
  expect(result).not.toContain('<img');
  expect(result).not.toContain('<svg>');
  expect(result).toContain('Предварительный расчёт');
});
