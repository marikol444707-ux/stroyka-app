import { createWarehouseCrudActions } from './warehouseCrudActions';

const createActions = overrides => createWarehouseCrudActions({
  API: '/api',
  editingItem: null,
  newTool: {name: 'Штукатурная станция', inventoryNumber: '', cost: '1000', status: 'На складе', location: 'Основной склад', project: '', masterId: '', masterName: '', issueType: '', notes: ''},
  refreshData: jest.fn(),
  setEditingItem: jest.fn(),
  setNewTool: jest.fn(),
  setShowForm: jest.fn(),
  ...overrides,
});

beforeEach(() => {
  global.alert = jest.fn();
});

test('saveTool keeps the form open and explains a failed API response', async () => {
  global.fetch = jest.fn(async () => ({ok: false, json: async () => ({detail: 'Нет выбранной компании'})}));
  const refreshData = jest.fn();
  const setShowForm = jest.fn();
  const actions = createActions({refreshData, setShowForm});

  const saved = await actions.saveTool();

  expect(saved).toBe(false);
  expect(global.alert).toHaveBeenCalledWith('Нет выбранной компании');
  expect(refreshData).not.toHaveBeenCalled();
  expect(setShowForm).not.toHaveBeenCalledWith(false);
});

test('saveTool refreshes the warehouse after a successful save', async () => {
  global.fetch = jest.fn(async () => ({ok: true, json: async () => ({id: 4})}));
  const refreshData = jest.fn();
  const actions = createActions({refreshData});

  const saved = await actions.saveTool();

  expect(saved).toBe(true);
  expect(refreshData).toHaveBeenCalledWith('warehouse');
});

test('applyWarehouseMovement reports positions that need estimate review', async () => {
  global.fetch = jest
    .fn()
    .mockResolvedValueOnce({ok: true, json: async () => ({estimateControl: {needsReview: true}, estimateReviewTaskId: 81})})
    .mockResolvedValueOnce({ok: true, json: async () => ({estimateControl: {needsReview: false}})});
  const notify = jest.fn();
  const refreshData = jest.fn();
  const setNewMovement = jest.fn();
  const actions = createActions({
    newMovement: {
      fromLocation: 'Основной склад',
      toLocation: 'Объект 1',
      notes: 'Согласовано с заказчиком',
      selectedMaterials: [
        {name: 'Грунтовка', quantity: 5, unit: 'кг', workPackage: 'Отделка'},
        {name: 'Кабель', quantity: 20, unit: 'м', workPackage: 'Электрика'},
      ],
    },
    notify,
    refreshData,
    setNewMovement,
    user: {name: 'Кладовщик'},
  });

  await actions.applyWarehouseMovement();

  expect(global.fetch).toHaveBeenCalledTimes(2);
  expect(notify).toHaveBeenCalledWith('Перемещение выполнено · требуют сметного разбора: 1 · задачи созданы: 1', 'ai');
  expect(refreshData).toHaveBeenCalled();
  expect(setNewMovement).toHaveBeenCalled();
});

test('saveInvoiceNew preserves OCR supplier identity for automatic accounting linkage', async () => {
  const supplierIdentityError = 'Для новой карточки поставщика укажите ИНН (10 или 12 цифр) либо ОГРН/ОГРНИП (13 или 15 цифр)';
  global.fetch = jest.fn(async url => {
    if (url === '/api/suppliers') {
      return {ok: false, status: 422, json: async () => ({detail: supplierIdentityError})};
    }
    if (url === '/api/warehouse-invoices') {
      return {ok: true, status: 200, json: async () => ({id: 14555, accountingStatus: 'Нужно уточнение'})};
    }
    throw new Error('Unexpected request: ' + url);
  });
  const refreshData = jest.fn();
  const setNewInvoice = jest.fn();
  const setShowForm = jest.fn();
  const actions = createActions({
    addActivity: jest.fn(),
    calcVat: total => ({base: total / 1.22, vat: total - total / 1.22, total}),
    createInvoiceControlReviewTasksForInvoice: jest.fn(async () => 0),
    getProjectWorkPackageOptions: jest.fn(() => []),
    newInvoice: {
      number: '14555',
      date: '2026-08-13',
      supplierId: '',
      supplier: 'ООО "Старт-Строй"',
      newSupplierName: 'ООО "Старт-Строй"',
      supplierInn: '2632001234',
      supplierKpp: '263201001',
      supplierOgrn: '1022600001234',
      isNewSupplier: true,
      acceptedBy: 'Прораб',
      location: 'Кисловодск Лицей 4',
      project: 'Кисловодск Лицей 4',
      warehouseTarget: 'object',
      inventoryOnly: false,
      selectedAction: 'receive_to_warehouse',
      sourceType: 'scan_project_invoice',
      vat: 'С НДС 22%',
      totalBase: 77360.66,
      totalVat: 17019.34,
      totalWithVat: 94380,
      photos: ['/uploads/invoice-14555.jpg'],
      photoUrls: ['/uploads/invoice-14555.jpg'],
      pagesCount: 1,
      items: [{
        name: 'Штукатурка КНАУФ МП-75 30КГ',
        quantity: '270',
        unit: 'шт',
        price: '336',
        lineTotal: '90720',
        workPackage: 'Отделка',
      }],
    },
    notify: jest.fn(),
    refreshData,
    setNewInvoice,
    setShowForm,
    suppliers: [],
    user: {name: 'Прораб'},
  });

  const saved = await actions.saveInvoiceNew();

  expect(global.fetch).toHaveBeenCalledTimes(1);
  const [url, request] = global.fetch.mock.calls[0];
  expect(url).toBe('/api/warehouse-invoices');
  expect(JSON.parse(request.body)).toEqual(expect.objectContaining({
    number: '14555',
    supplierId: null,
    supplierName: 'ООО "Старт-Строй"',
    supplierInn: '2632001234',
    supplierKpp: '263201001',
    supplierOgrn: '1022600001234',
    sourceType: 'scan_project_invoice',
    syncSupplierInvoice: true,
  }));
  expect(saved).toBe(true);
  expect(global.alert).not.toHaveBeenCalledWith(supplierIdentityError);
  expect(refreshData).toHaveBeenCalled();
  expect(setNewInvoice).toHaveBeenCalled();
  expect(setShowForm).toHaveBeenCalledWith(false);
});

test('saveInvoiceNew cancels a duplicate upload and shows the server explanation', async () => {
  const duplicateMessage = 'Эта накладная уже есть в базе. Повторная загрузка отменена.';
  global.fetch = jest.fn(async () => ({
    ok: false,
    status: 409,
    json: async () => ({detail: duplicateMessage}),
  }));
  const notify = jest.fn();
  const addActivity = jest.fn();
  const refreshData = jest.fn();
  const setNewInvoice = jest.fn();
  const setShowForm = jest.fn();
  const actions = createActions({
    addActivity,
    calcVat: total => ({base: total, vat: 0, total}),
    createInvoiceControlReviewTasksForInvoice: jest.fn(async () => 0),
    getProjectWorkPackageOptions: jest.fn(() => []),
    newInvoice: {
      number: '№ 14555',
      date: '2026-08-10',
      supplierId: '77',
      acceptedBy: 'Прораб',
      location: 'Объект 2',
      project: 'Объект 2',
      warehouseTarget: 'object',
      sourceType: 'scan_project_invoice',
      vat: 'Без НДС',
      totalBase: 94380,
      totalVat: 0,
      totalWithVat: 94380,
      items: [{name: 'Штукатурка', quantity: 270, unit: 'шт', price: 349.56, lineTotal: 94380}],
    },
    notify,
    refreshData,
    setNewInvoice,
    setShowForm,
    suppliers: [{id: 77, name: 'ООО Поставка'}],
    user: {name: 'Прораб'},
  });

  const saved = await actions.saveInvoiceNew();

  expect(saved).toBe(false);
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(global.alert).toHaveBeenCalledWith(duplicateMessage);
  expect(notify).not.toHaveBeenCalled();
  expect(addActivity).not.toHaveBeenCalled();
  expect(refreshData).not.toHaveBeenCalled();
  expect(setNewInvoice).not.toHaveBeenCalled();
  expect(setShowForm).not.toHaveBeenCalledWith(false);
});

test('saveInvoiceNew does not link a name-only OCR supplier to a colliding normalized supplier card', async () => {
  global.fetch = jest.fn(async url => {
    if (url === '/api/warehouse-invoices') {
      return {ok: true, status: 200, json: async () => ({id: 14556, accountingStatus: 'Нужно уточнение'})};
    }
    throw new Error('Unexpected request: ' + url);
  });
  const actions = createActions({
    addActivity: jest.fn(),
    calcVat: total => ({base: total, vat: 0, total}),
    createInvoiceControlReviewTasksForInvoice: jest.fn(async () => 0),
    getProjectWorkPackageOptions: jest.fn(() => []),
    newInvoice: {
      number: '14556',
      date: '2026-08-13',
      supplierId: '',
      supplier: 'ООО "Старт-Строй"',
      newSupplierName: 'ООО "Старт-Строй"',
      isNewSupplier: true,
      acceptedBy: 'Прораб',
      location: 'Кисловодск Лицей 4',
      project: 'Кисловодск Лицей 4',
      warehouseTarget: 'object',
      inventoryOnly: false,
      selectedAction: 'receive_to_warehouse',
      sourceType: 'scan_project_invoice',
      vat: 'Без НДС',
      totalBase: 1000,
      totalVat: 0,
      totalWithVat: 1000,
      photos: ['/uploads/invoice-14556.jpg'],
      photoUrls: ['/uploads/invoice-14556.jpg'],
      pagesCount: 1,
      items: [{name: 'Штукатурка', quantity: '10', unit: 'шт', price: '100', lineTotal: '1000'}],
    },
    notify: jest.fn(),
    refreshData: jest.fn(),
    setNewInvoice: jest.fn(),
    setShowForm: jest.fn(),
    suppliers: [{id: 77, name: 'ИП Старт-Строй'}],
    user: {name: 'Прораб'},
  });

  const saved = await actions.saveInvoiceNew();

  expect(saved).toBe(true);
  expect(global.fetch).toHaveBeenCalledTimes(1);
  const [url, request] = global.fetch.mock.calls[0];
  expect(url).toBe('/api/warehouse-invoices');
  expect(JSON.parse(request.body)).toEqual(expect.objectContaining({
    supplierId: null,
    supplierName: 'ООО "Старт-Строй"',
  }));
});

test('saveInvoiceNew keeps an explicitly selected supplier card', async () => {
  global.fetch = jest.fn(async url => {
    if (url === '/api/warehouse-invoices') {
      return {ok: true, status: 200, json: async () => ({id: 14557})};
    }
    throw new Error('Unexpected request: ' + url);
  });
  const actions = createActions({
    addActivity: jest.fn(),
    calcVat: total => ({base: total, vat: 0, total}),
    createInvoiceControlReviewTasksForInvoice: jest.fn(async () => 0),
    getProjectWorkPackageOptions: jest.fn(() => []),
    newInvoice: {
      number: '14557',
      date: '2026-08-13',
      supplierId: '77',
      supplier: '',
      newSupplierName: '',
      isNewSupplier: false,
      acceptedBy: 'Прораб',
      location: 'Кисловодск Лицей 4',
      project: 'Кисловодск Лицей 4',
      warehouseTarget: 'object',
      inventoryOnly: false,
      selectedAction: 'receive_to_warehouse',
      sourceType: 'manual_project_invoice',
      vat: 'Без НДС',
      totalBase: 1000,
      totalVat: 0,
      totalWithVat: 1000,
      items: [{name: 'Штукатурка', quantity: '10', unit: 'шт', price: '100'}],
    },
    notify: jest.fn(),
    refreshData: jest.fn(),
    setNewInvoice: jest.fn(),
    setShowForm: jest.fn(),
    suppliers: [{id: 77, name: 'ООО Проверенный', inn: '2312254452'}],
    user: {name: 'Прораб'},
  });

  expect(await actions.saveInvoiceNew()).toBe(true);

  expect(global.fetch).toHaveBeenCalledTimes(1);
  const body = JSON.parse(global.fetch.mock.calls[0][1].body);
  expect(body).toEqual(expect.objectContaining({
    supplierId: 77,
    supplierName: 'ООО Проверенный',
  }));
});
