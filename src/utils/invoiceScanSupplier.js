export function resolveInvoiceScanSupplier(parsedSupplier, recognition = {}) {
  const supplierId = Number(recognition?.supplierId);
  const normalizedSupplierId = Number.isInteger(supplierId) && supplierId > 0 ? supplierId : '';
  const supplierName = String(parsedSupplier || recognition?.supplierName || '').trim();

  return {
    supplierId: normalizedSupplierId,
    isNewSupplier: Boolean(supplierName) && !normalizedSupplierId,
  };
}
