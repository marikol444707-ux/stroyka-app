import { createDataLoadActions } from './dataLoadActions';

const response = (data, ok = true) => ({ ok, json: async () => data });
const setup = () => {
  const setPricelistItems = jest.fn();
  return { setPricelistItems, ...createDataLoadActions({ API: '/api', setPricelistItems }) };
};
afterEach(() => jest.restoreAllMocks());

test.each([null, undefined, ''])('clearing the project does not request an invalid pricelist: %s', async id => {
  global.fetch = jest.fn();
  const { loadPricelistItems, setPricelistItems } = setup();
  expect(await loadPricelistItems(id)).toEqual({ items: [], error: '' });
  expect(fetch).not.toHaveBeenCalled();
  expect(setPricelistItems).toHaveBeenLastCalledWith([]);
});

test.each([
  response({ detail: 'Нет доступа к прайс-листу' }, false),
  response({ detail: 'Неизвестный формат' }),
  { ok: false, json: async () => { throw new Error('Not JSON'); } },
])('an error response never becomes a work list', async reply => {
  global.fetch = jest.fn(async () => reply);
  const { loadPricelistItems, setPricelistItems } = setup();
  const result = await loadPricelistItems(12);
  expect(result.items).toEqual([]);
  expect(result.error).toBeTruthy();
  expect(setPricelistItems.mock.calls.every(([items]) => Array.isArray(items))).toBe(true);
});

test('a network failure is reported without an unhandled rejection', async () => {
  global.fetch = jest.fn(async () => { throw new Error('Offline'); });
  expect(await setup().loadPricelistItems(12)).toEqual({ items: [], error: 'Offline' });
});

test('loads the successful array', async () => {
  const items = [{ id: 1, name: 'Кабель' }];
  global.fetch = jest.fn(async () => response(items));
  const { loadPricelistItems, setPricelistItems } = setup();
  expect(await loadPricelistItems(12)).toEqual({ items, error: '' });
  expect(setPricelistItems).toHaveBeenLastCalledWith(items);
});

test('an older project response cannot replace the newly selected project', async () => {
  let resolveOld;
  global.fetch = jest.fn().mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }))
    .mockResolvedValueOnce(response([{ id: 2 }]));
  const { loadPricelistItems, setPricelistItems } = setup();
  const old = loadPricelistItems(1);
  await loadPricelistItems(2);
  resolveOld(response([{ id: 1 }]));
  await old;
  expect(setPricelistItems).toHaveBeenLastCalledWith([{ id: 2 }]);
});

test('clearing invalidates a pending project request', async () => {
  let resolveOld;
  global.fetch = jest.fn(() => new Promise(resolve => { resolveOld = resolve; }));
  const { loadPricelistItems, setPricelistItems } = setup();
  const old = loadPricelistItems(1);
  const newRender = createDataLoadActions({ API: '/api', setPricelistItems });
  await newRender.loadPricelistItems(null);
  resolveOld(response([{ id: 1 }]));
  await old;
  expect(setPricelistItems).toHaveBeenLastCalledWith([]);
});
