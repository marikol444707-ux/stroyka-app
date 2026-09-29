export const isInvoiceLineIndex = value => Number.isSafeInteger(value) && value >= 0;

// Never reconstruct identity from the position in a permission-filtered response.
export function identifiedInvoiceLines(items) {
  if (!Array.isArray(items)) return [];
  const counts = new Map();
  items.forEach(item => {
    const index = item?.invoiceLineIndex;
    if (isInvoiceLineIndex(index)) counts.set(index, (counts.get(index) || 0) + 1);
  });
  return items.filter(item => isInvoiceLineIndex(item?.invoiceLineIndex)
    && counts.get(item.invoiceLineIndex) === 1);
}
