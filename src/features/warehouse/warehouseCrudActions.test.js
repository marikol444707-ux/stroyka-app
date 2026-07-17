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
