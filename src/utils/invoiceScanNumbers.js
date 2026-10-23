const AMOUNT_SEPARATOR = /[,.]/;

export function parseInvoiceNumber(value) {
  if (value === null || value === undefined || value === '') return 0;
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0;

  let normalized = String(value)
    .replace(/[\s\u00a0\u202f]/g, '')
    .replace(/руб(?:\.|лей|ля)?|RUB|₽/gi, '')
    .replace(/[^\d,.\-+]/g, '');
  if (!normalized || !/^[+-]?\d[\d,.]*$/.test(normalized)) return 0;

  const sign = /^[+-]/.test(normalized) ? normalized[0] : '';
  normalized = normalized.replace(/^[+-]/, '');
  const separators = [...normalized.matchAll(/[,.]/g)];
  if (separators.length) {
    const last = separators[separators.length - 1];
    const hasBothKinds = normalized.includes(',') && normalized.includes('.');
    const decimalPosition = last.index;
    const groups = normalized.split(AMOUNT_SEPARATOR);
    const isThousandsOnly = !hasBothKinds
      && separators.length > 1
      && groups.slice(1).every(group => group.length === 3);

    if (isThousandsOnly) {
      normalized = normalized.replace(/[,.]/g, '');
    } else {
      const integer = normalized.slice(0, decimalPosition).replace(/[,.]/g, '');
      const fraction = normalized.slice(decimalPosition + 1).replace(/[,.]/g, '');
      normalized = `${integer}.${fraction}`;
    }
  }

  const parsed = Number(`${sign}${normalized}`);
  return Number.isFinite(parsed) ? parsed : 0;
}
