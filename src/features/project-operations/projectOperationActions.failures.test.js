import { createProjectOperationActions } from './projectOperationActions';

const setup = (extra = {}) => {
  const ctx = {
    API: '/api', notify: jest.fn(), refreshData: jest.fn(),
    newRoom: { name: 'Кухня', project: 'Учебный объект' }, customRoomTypes: [],
    draftRoomWindows: [], draftRoomDoors: [], setNewRoom: jest.fn(), setEditingItem: jest.fn(),
    setDraftRoomWindows: jest.fn(), setDraftRoomDoors: jest.fn(),
    setShowRoomForm: jest.fn(), setExpandedRoom: jest.fn(),
    newStage: { name: 'Этап' }, setNewStage: jest.fn(),
    newWindow: {width: 1, height: 2, windowType: 'ПВХ'}, roomWindows: [],
    setRoomWindows: jest.fn(), setNewWindow: jest.fn(),
    setTbJournal: jest.fn(), tbJournal: [], user: {name: 'Тест'},
    ...extra,
  };
  return { ctx, actions: createProjectOperationActions(ctx) };
};
afterEach(() => jest.restoreAllMocks());

test.each(['saveRoom', 'saveProjectStage', 'saveWindow', 'deleteWindow', 'saveTbEntry'])('%s preserves local data on rejected save', async action => {
  global.fetch = jest.fn(async () => ({ok: false, json: async () => ({detail: 'Отказ'})}));
  const {ctx, actions} = setup();
  await expect(actions[action]({project: 'Учебный объект'})).resolves.toBe(false);
  expect(ctx.notify).toHaveBeenCalledWith('Отказ', 'error');
  for (const name of ['setNewRoom','setNewStage','setRoomWindows','setNewWindow','setTbJournal','refreshData']) {
    expect(ctx[name]).not.toHaveBeenCalled();
  }
});

test('network failure does not invent a window', async () => {
  global.fetch = jest.fn(async () => {throw new Error('offline');});
  const {ctx, actions} = setup();
  await actions.saveWindow(7);
  expect(ctx.setRoomWindows).not.toHaveBeenCalled();
  expect(ctx.setNewWindow).not.toHaveBeenCalled();
});

test('confirmed window keeps the real server identity and display fields', async () => {
  global.fetch = jest.fn(async () => ({ok: true, json: async () => [18,7,'Окно']}));
  const {ctx, actions} = setup();
  await actions.saveWindow(7);
  expect(ctx.setRoomWindows.mock.calls[0][0]([])[0]).toMatchObject({id: 18, room_id: 7, window_type: 'ПВХ'});
  expect(ctx.setNewWindow).toHaveBeenCalledTimes(1);
});

test('child failure retains confirmed room identity and pending drafts', async () => {
  global.fetch = jest.fn()
    .mockResolvedValueOnce({ok: true, json: async () => ({id: 9})})
    .mockResolvedValueOnce({ok: false, json: async () => ({detail: 'Не сохранено'})});
  const {ctx, actions} = setup({draftRoomWindows: [{width:1,height:1}]});
  await actions.saveRoom();
  expect(ctx.setEditingItem).toHaveBeenCalledWith(expect.objectContaining({id: 9}));
  expect(ctx.setDraftRoomWindows).not.toHaveBeenCalled();
  expect(ctx.setNewRoom).not.toHaveBeenCalled();
});
