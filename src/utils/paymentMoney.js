// Match the backend money bound; parse decimal digits without rounding input.
export function paymentKopecks(value) {
  if (typeof value !== 'string' && typeof value !== 'number') return null;
  const match = /^(\d{1,12})(?:[.,](\d{1,2}))?$/.exec(String(value).trim());
  if (!match) return null;
  return Number(match[1]) * 100 + Number((match[2] || '').padEnd(2, '0'));
}

export const paymentLabel = kopecks => (kopecks / 100).toLocaleString('ru-RU', {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});
