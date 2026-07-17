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
