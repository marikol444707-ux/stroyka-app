const todayIso = () => new Date().toISOString().split('T')[0];

export const createSupplyRequestForm = (overrides = {}) => ({
  items: [{materialName: '', quantity: '', unit: 'шт', workPackage: ''}],
  project: '',
  urgency: 'обычная',
  notes: '',
  category: '',
  ...overrides,
});

export const createKpResponseForm = (overrides = {}) => ({
  pricePerUnit: '',
  deliveryDays: '',
  paymentTerms: 'Постоплата',
  vatIncluded: true,
  validUntil: '',
  supplierMessage: '',
  pdfUrl: '',
  ...overrides,
});

export const createOfferInvoiceForm = (overrides = {}) => ({
  invoiceNumber: '',
  invoiceDate: todayIso(),
  amount: '',
  vatAmount: '',
  description: '',
  fileUrl: '',
  ...overrides,
});

export const createShipmentForm = (overrides = {}) => ({
  shippedQuantity: '',
  waybillNumber: '',
  waybillDate: todayIso(),
  vehicleNumber: '',
  driverName: '',
  documentUrl: '',
  photoUrl: '',
  ...overrides,
});

export const createReceiveForm = (overrides = {}) => ({
  receivedQuantity: '',
  qualityStatus: 'Принято',
  qualityNotes: '',
  photoUrl: '',
  claimDescription: '',
  ...overrides,
});

export const createSupplierInviteForm = (overrides = {}) => ({
  presetName: '',
  presetCategory: 'Сыпучие и бетон',
  supplierId: null,
  expiresInDays: 14,
  ...overrides,
});

export const createSupplierForm = (overrides = {}) => ({
  name: '',
  phone: '',
  email: '',
  specialization: '',
  category: 'Сыпучие и бетон',
  rating: 5.0,
  status: 'Активный',
  ...overrides,
});

export const createSupplierOfferForm = (overrides = {}) => ({
  supplierId: '',
  pricePerUnit: '',
  deliveryDays: '',
  notes: '',
  ...overrides,
});

export const createRequestForm = (overrides = {}) => ({
  items: [{materialName: '', quantity: '', unit: 'шт', workPackage: ''}],
  project: '',
  notes: '',
  selectedSuppliers: [],
  category: '',
  ...overrides,
});

export const createSupplierInvoiceForm = (overrides = {}) => ({
  supplierName: '',
  projectName: '',
  workPackage: '',
  invoiceNumber: '',
  invoiceDate: '',
  amount: '',
  vatAmount: '',
  description: '',
  ...overrides,
});
