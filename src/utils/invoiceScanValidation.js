// Check current draft values without guessing quantities or merging equal names.
export function invoiceScanNumber(value) {
  if (value === null || value === undefined || typeof value === 'boolean' || value === '') return null;
  let text = String(value).replace(/\s+/g, '').replace(/₽/g, '').replace(/руб\.?$/i, '');
  if (text.includes(',') && text.includes('.')) {
    text = text.lastIndexOf(',') > text.lastIndexOf('.') ? text.replace(/\./g, '').replace(',', '.') : text.replace(/,/g, '');
  } else text = text.replace(',', '.');
  if (!/^-?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) return null;
  const result = Number(text);
  return Number.isFinite(result) && Math.abs(result) <= 1e15 ? result : null;
}

const first = (data, keys) => {
  for (const key of keys) if (data[key] !== undefined && data[key] !== null && data[key] !== '') return invoiceScanNumber(data[key]);
  return null;
};
const present = (data, keys) => keys.some(key => data[key] !== undefined && data[key] !== null && data[key] !== '');

export function validateInvoiceScan(payload = {}) {
  const errors = [];
  const items = Array.isArray(payload.items) ? payload.items : [];
  let itemsTotal = 0;
  items.forEach((item, index) => {
    if (!item || !String(item.name || '').trim()) return;
    const row = index + 1;
    const quantity = first(item, ['quantity', 'qty']);
    const price = first(item, ['priceWithVat', 'price_with_vat', 'price', 'unitPrice', 'unit_price']);
    let total = first(item, ['lineTotalWithVat', 'line_total_with_vat', 'lineTotal', 'line_total', 'total']);
    const invalidTotal = total === null && present(item, ['lineTotalWithVat', 'line_total_with_vat', 'lineTotal', 'line_total', 'total']);
    if (quantity === null || quantity <= 0 || price === null || price < 0 || invalidTotal || (total !== null && total < 0)) {
      errors.push({code:'invalid_line', row, message:`Строка ${row}: проверьте количество, цену и сумму.`});
      return;
    }
    const calculated = quantity * price;
    if (total === null) total = calculated;
    const places = Math.min(4, Math.max(2, (String(price).split('.')[1] || '').length));
    const tolerance = Math.abs(quantity) * 10 ** -places / 2 + 0.01;
    if (Math.abs(total - calculated) > tolerance + 1e-7) {
      errors.push({code:'line_total_mismatch', row, message:`Строка ${row}: количество × цена не совпадает с суммой строки.`});
    }
    itemsTotal += total;
  });
  const documentTotal = first(payload, ['totalWithVat', 'total_with_vat', 'grandTotal', 'total']);
  if ((documentTotal === null && present(payload, ['totalWithVat', 'total_with_vat', 'grandTotal', 'total'])) || documentTotal < 0) {
    errors.push({code:'invalid_document_total',message:'Проверьте итог документа.'});
  }
  if (documentTotal > 0 && Math.abs(itemsTotal - documentTotal) > Math.max(0.02, items.length * 0.01) + 1e-7) {
    errors.push({code:'document_total_mismatch', message:'Сумма строк не совпадает с итогом документа. Сверьте количество, цену и НДС с оригиналом.'});
  }
  const base = first(payload, ['totalBase', 'total_base']);
  const vat = first(payload, ['totalVat', 'total_vat']);
  if (documentTotal > 0 && base !== null && vat !== null && Math.abs(base + vat - documentTotal) > 0.02 + 1e-7) {
    errors.push({code:'tax_total_mismatch',message:'Сумма без НДС и НДС не совпадают с итогом документа.'});
  }
  return {valid:errors.length === 0, errors, itemsTotal:Math.round(itemsTotal * 100) / 100, documentTotal};
}

export const isScannedInvoiceDraft = invoice => String(invoice?.sourceType || '').startsWith('scan_')
  || Boolean(invoice?.scanDocumentType || invoice?.scanWarnings || invoice?.scanRecognition);
