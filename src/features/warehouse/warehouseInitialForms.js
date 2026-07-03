const todayIso = () => new Date().toISOString().split('T')[0];

export const createCatalogItemForm = (overrides = {}) => ({
  materialName: '',
  unit: 'шт',
  price: '',
  minQuantity: '1',
  deliveryDays: '3',
  notes: '',
  ...overrides,
});

export const createSupplierRequisitesForm = (overrides = {}) => ({
  companyName: '',
  inn: '',
  kpp: '',
  address: '',
  bank: '',
  bik: '',
  account: '',
  phone: '',
  email: '',
  priceUrl: '',
  ...overrides,
});

export const createMaterialTransferForm = (overrides = {}) => ({
  materialName: '',
  quantity: '',
  unit: 'шт',
  workPackage: '',
  toPerson: '',
  toPersonRole: '',
  toUserId: '',
  fromLocation: 'Основной склад',
  notes: '',
  transferDate: todayIso(),
  ...overrides,
});

export const createWarehouseForm = (overrides = {}) => ({
  name: '',
  city: '',
  address: '',
  notes: '',
  ...overrides,
});

export const createWarehouseMovementForm = (overrides = {}) => ({
  materialName: '',
  fromLocation: 'Основной склад',
  toLocation: '',
  quantity: '',
  unit: 'шт',
  notes: '',
  selectedMaterials: [],
  ...overrides,
});

export const createWarehouseInvoiceItemForm = (overrides = {}) => ({
  name: '',
  quantity: '',
  unit: 'шт',
  price: '',
  category: '',
  workPackage: '',
  ...overrides,
});

export const createWarehouseInvoiceForm = (overrides = {}) => ({
  number: '',
  date: '',
  supplierId: '',
  isNewSupplier: false,
  newSupplierName: '',
  acceptedBy: '',
  location: 'Основной склад',
  project: '',
  warehouseTarget: 'main',
  selectedAction: 'receive_to_warehouse',
  sourceType: 'manual_main_invoice',
  sourceId: null,
  vat: 'Без НДС',
  photos: [],
  photoUrls: [],
  pagesCount: 1,
  items: [createWarehouseInvoiceItemForm()],
  ...overrides,
});

export const createToolForm = (overrides = {}) => ({
  name: '',
  inventoryNumber: '',
  cost: '',
  status: 'На складе',
  location: 'Основной склад',
  project: '',
  masterId: '',
  masterName: '',
  issueType: '',
  notes: '',
  ...overrides,
});

export const createInventoryForm = (overrides = {}) => ({
  project: '',
  date: '',
  notes: '',
  ...overrides,
});

export const createIssueToolForm = (overrides = {}) => ({
  masterName: '',
  project: '',
  issueType: 'Временно',
  ...overrides,
});
