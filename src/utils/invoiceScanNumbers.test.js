import {parseInvoiceNumber} from './invoiceScanNumbers';

test.each([
  ['263.50', 263.5],
  ['263,50', 263.5],
  ['1 263,50 ₽', 1263.5],
  ['1.263,50', 1263.5],
  ['1,263.50', 1263.5],
  ['12 000', 12000],
  ['-12,75', -12.75],
  ['', 0],
  ['не число', 0],
])('parses invoice amount %s', (input, expected) => {
  expect(parseInvoiceNumber(input)).toBe(expected);
});

test('keeps numeric JSON amounts unchanged', () => {
  expect(parseInvoiceNumber(263.5)).toBe(263.5);
});
