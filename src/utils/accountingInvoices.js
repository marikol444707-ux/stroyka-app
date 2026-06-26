export const ACCOUNTING_INVOICE_STATUSES = [
  'Нет фото',
  'На проверке',
  'Нужно уточнение',
  'К оплате',
  'Частично оплачена',
  'Оплачена',
  'Отклонена',
];

export const accountingStatusGroupLabels = {
  'Нет фото': 'Нет фото',
  'На проверке': 'На проверке',
  'Нужно уточнение': 'Нужно уточнение',
  'К оплате': 'К оплате',
  'Частично оплачена': 'Частично оплачены',
  'Оплачена': 'Оплачены',
  'Отклонена': 'Отклонены',
};

export const invoicePhotos = (invoice = {}) => {
  const fromArray = Array.isArray(invoice.photos) ? invoice.photos : [];
  const fromPhotoUrls = Array.isArray(invoice.photoUrls) ? invoice.photoUrls : [];
  return [...fromArray, ...fromPhotoUrls, invoice.photoUrl]
    .map(value => String(value || '').trim())
    .filter(Boolean)
    .filter((value, index, list) => list.indexOf(value) === index);
};

export const invoiceAmount = (invoice = {}) => {
  const itemSum = (invoice.items || []).reduce((sum, item) => {
    const lineTotal = Number(item.lineTotal || item.line_total || item.total || 0);
    const qty = Number(item.quantity || 0);
    const price = Number(item.priceWithVat || item.price_with_vat || item.price || 0);
    return sum + (lineTotal || qty * price || 0);
  }, 0);
  return Number(invoice.totalWithVat || invoice.total_with_vat || invoice.total || invoice.amount || invoice.totalBase || itemSum || 0);
};

export const invoicePaidAmount = (invoice = {}) => Number(invoice.paidAmount || invoice.paid_amount || 0);

export const invoiceDebtAmount = (invoice = {}) => {
  const amount = invoiceAmount(invoice);
  const paid = invoicePaidAmount(invoice);
  return Math.max(0, Math.round((amount - paid) * 100) / 100);
};

export const invoiceAccountingStatus = (invoice = {}, controls = []) => {
  const amount = invoiceAmount(invoice);
  const paid = invoicePaidAmount(invoice);
  if (amount > 0 && paid + 0.01 >= amount) return 'Оплачена';
  if (paid > 0 && (!amount || paid < amount - 0.01)) return 'Частично оплачена';
  const stored = String(invoice.accountingStatus || invoice.accounting_status || '').trim();
  if (stored) return stored;
  if (invoicePhotos(invoice).length === 0) return 'Нет фото';
  const issueRows = (controls || []).filter(row => ['danger', 'warning'].includes(row.severity));
  return issueRows.length ? 'На проверке' : 'На проверке';
};

export const buildAccountingInvoiceRows = (invoices = [], controlFn) => (
  (invoices || [])
    .filter(invoice => String(invoice.status || '') !== 'Аннулирована')
    .map(invoice => {
      const controls = typeof controlFn === 'function'
        ? (controlFn(invoice) || []).filter(row => row && row.name)
        : [];
      const issueRows = controls.filter(row => ['danger', 'warning'].includes(row.severity));
      const photos = invoicePhotos(invoice);
      const amount = invoiceAmount(invoice);
      const paidAmount = invoicePaidAmount(invoice);
      const debt = invoiceDebtAmount(invoice);
      return {
        invoice,
        controls,
        issueRows,
        photos,
        amount,
        paidAmount,
        debt,
        status: invoiceAccountingStatus(invoice, controls),
      };
    })
);
