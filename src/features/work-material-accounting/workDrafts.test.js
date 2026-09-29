import { clearSubmittedDrafts } from './workDrafts';

const copy = value => JSON.parse(JSON.stringify(value));
const materials = [{ name: 'Клей', unit: 'кг', quantity: 4, personalQuantity: 2, warehouseQuantity: 2 }];
const params = { roomName: 'Кабинет 1', comment: 'Выполнено', photoUrl: '/uploads/synthetic.jpg' };
const estimate = (key = '4:0:0') => ({ kind: 'estimate', key, done: '2', materials: copy(materials), params: copy(params) });
const pricelist = (key = '8') => ({ kind: 'pricelist', key, selection: { quantity: '2', materials: copy(materials) } });

function captureState(initial, refValues = initial.estimateDoneDrafts || {}) {
  const state = {
    estimateDoneDrafts: {}, estimateWorkMaterials: {}, estimateWorkParams: {}, selectedWorks: {},
    ...copy(initial),
  };
  const bindings = { estimateDraftValueRef: { current: copy(refValues) } };
  for (const key of Object.keys(state)) {
    bindings['set' + key[0].toUpperCase() + key.slice(1)] = jest.fn(update => {
      expect(typeof update).toBe('function');
      state[key] = update(Object.freeze(state[key]));
    });
  }
  return { state, bindings };
}

test('clears only the completed command prefix and keeps rejected tail and unrelated drafts', () => {
  const completed = estimate();
  const tail = estimate('4:0:1');
  const { state, bindings } = captureState({
    estimateDoneDrafts: { [completed.key]: '2', [tail.key]: '2', unrelated: '9' },
    estimateWorkMaterials: { [completed.key]: copy(materials), [tail.key]: copy(materials), unrelated: [] },
    estimateWorkParams: { [completed.key]: copy(params), [tail.key]: copy(params), unrelated: { comment: 'Ещё не отправлено' } },
    selectedWorks: { '8': pricelist().selection },
  });
  const batch = { next: 1, rejected: true, commands: [{ drafts: [completed] }, { drafts: [tail] }] };
  const savedBatch = copy(batch);
  clearSubmittedDrafts(batch, bindings);
  expect(state.estimateDoneDrafts).toEqual({ [tail.key]: '2', unrelated: '9' });
  expect(state.estimateWorkMaterials).toEqual({ [tail.key]: materials, unrelated: [] });
  expect(state.estimateWorkParams).toEqual({ [tail.key]: params, unrelated: { comment: 'Ещё не отправлено' } });
  expect(state.selectedWorks).toEqual({ '8': pricelist().selection });
  expect(bindings.estimateDraftValueRef.current).toEqual({ [tail.key]: '2', unrelated: '9' });
  expect(batch).toEqual(savedBatch);
});

test('an unknown first reply leaves every form draft intact until a command is confirmed', () => {
  const draft = estimate();
  const { state, bindings } = captureState({
    estimateDoneDrafts: { [draft.key]: draft.done },
    estimateWorkMaterials: { [draft.key]: copy(draft.materials) },
    estimateWorkParams: { [draft.key]: copy(draft.params) },
    selectedWorks: { '8': pricelist().selection },
  });
  const before = copy(state);
  clearSubmittedDrafts({ next: 0, commands: [{ attempted: true, drafts: [draft, pricelist()] }] }, bindings);
  expect(state).toEqual(before);
  expect(bindings.estimateDraftValueRef.current).toEqual(before.estimateDoneDrafts);
});

test('edits made while a reply was unknown survive successful recovery field by field', () => {
  const draft = estimate();
  const newParams = { ...params, comment: 'Добавлено после потери связи' };
  const newSelection = { ...pricelist().selection, quantity: '3' };
  const { state, bindings } = captureState({
    estimateDoneDrafts: { [draft.key]: '3' },
    estimateWorkMaterials: { [draft.key]: copy(materials) },
    estimateWorkParams: { [draft.key]: newParams },
    selectedWorks: { '8': newSelection },
  });
  clearSubmittedDrafts({ next: 1, commands: [{ drafts: [draft, pricelist()] }] }, bindings);
  expect(state.estimateDoneDrafts).toEqual({ [draft.key]: '3' });
  expect(state.estimateWorkMaterials).toEqual({});
  expect(state.estimateWorkParams).toEqual({ [draft.key]: newParams });
  expect(state.selectedWorks).toEqual({ '8': newSelection });
  expect(bindings.estimateDraftValueRef.current).toEqual({ [draft.key]: '3' });
});

test('a changed material row survives while matching quantity and room fields are cleared', () => {
  const draft = estimate();
  const editedMaterials = [{ ...materials[0], quantity: 5, warehouseQuantity: 3 }];
  const { state, bindings } = captureState({
    estimateDoneDrafts: { [draft.key]: draft.done },
    estimateWorkMaterials: { [draft.key]: editedMaterials },
    estimateWorkParams: { [draft.key]: copy(params) },
  }, { [draft.key]: '3' });
  clearSubmittedDrafts({ next: 1, commands: [{ drafts: [draft] }] }, bindings);
  expect(state.estimateDoneDrafts).toEqual({});
  expect(state.estimateWorkMaterials).toEqual({ [draft.key]: editedMaterials });
  expect(state.estimateWorkParams).toEqual({});
  expect(bindings.estimateDraftValueRef.current).toEqual({ [draft.key]: '3' });
});

test('completed commands selectively clear multiple estimate and pricelist forms using JSON values', () => {
  const first = estimate();
  const second = estimate('5:0:0');
  const { state, bindings } = captureState({
    estimateDoneDrafts: { [first.key]: '2', [second.key]: '2', keep: '2' },
    estimateWorkMaterials: { [first.key]: copy(materials), [second.key]: copy(materials), keep: copy(materials) },
    estimateWorkParams: { [first.key]: copy(params), [second.key]: copy(params), keep: copy(params) },
    selectedWorks: { '8': copy(pricelist('8').selection), '9': copy(pricelist('9').selection), keep: { quantity: '1' } },
  });
  const batch = { next: 2, commands: [
    { drafts: [first, pricelist('8')] }, { drafts: [second, pricelist('9')] },
  ] };
  clearSubmittedDrafts(batch, bindings);
  expect(state).toEqual({
    estimateDoneDrafts: { keep: '2' }, estimateWorkMaterials: { keep: materials },
    estimateWorkParams: { keep: params }, selectedWorks: { keep: { quantity: '1' } },
  });
  expect(bindings.estimateDraftValueRef.current).toEqual({ keep: '2' });
});

test('different JSON scalar types are preserved instead of being treated as matching drafts', () => {
  const draft = estimate();
  const { state, bindings } = captureState({ estimateDoneDrafts: { [draft.key]: 2 } });
  clearSubmittedDrafts({ next: 1, commands: [{ drafts: [draft] }] }, bindings);
  expect(state.estimateDoneDrafts).toEqual({ [draft.key]: 2 });
  expect(bindings.estimateDraftValueRef.current).toEqual({ [draft.key]: 2 });
});

test('older completed commands without recorded drafts cannot erase current form state', () => {
  const { state, bindings } = captureState({ estimateDoneDrafts: { '4:0:0': '2' }, selectedWorks: { '8': { quantity: '2' } } });
  const before = copy(state);
  clearSubmittedDrafts({ next: 1, commands: [{ payload: { quantity: 2 } }] }, bindings);
  expect(state).toEqual(before);
  expect(bindings.estimateDraftValueRef.current).toEqual(before.estimateDoneDrafts);
});
