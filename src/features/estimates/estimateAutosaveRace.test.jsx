import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import EstimateSaveNotice from '../../components/EstimateSaveNotice';
import EstimateSectionsEditor from '../../components/EstimateSectionsEditor';
import { useAppMainState } from '../app-shell/useAppMainState';
import { persistEstimateAction } from './estimatePersistenceActions';

const estimate = id => ({
  id, revision: 1, name: `Смета ${id}`, sectionsLoaded: true,
  sections: [{id: 1, name: 'Монтаж', items: [
    {id: 10, itemType: 'work', name: `Работа ${id}`, unit: 'шт', quantity: 1, priceWork: 100},
  ]}],
});
const a = estimate(7);
const b = estimate(8);
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
};
const outcomes = ['success', 'http-error', 'network-error', 'conflict'];
let state, fetchFn, qualityReview, normReview, saves;

function Harness() {
  state = useAppMainState();
  if (!state.selectedEstimate) return <span>Смета закрыта</span>;
  return <><EstimateSaveNotice state={state.estimateSaveState} /><EstimateSectionsEditor
    selectedEstimate={state.selectedEstimate}
    setSelectedEstimate={state.setSelectedEstimate} setEstimatesList={state.setEstimatesList}
    persistEstimate={est => {
      const saving = persistEstimateAction({
        API: '/api', est, beginEstimateSave: state.beginEstimateSave, setEstimatesList: state.setEstimatesList, estimatesList: state.estimatesList, fetchFn,
        queueEstimateQualityReviewTask: qualityReview, queueEstimateNormReviewTask: normReview,
      });
      saves.push(saving);
      return saving;
    }}
    showEstimateIssuesOnly={false} estimateQualityRows={() => []} isMobile={false}
    mobileExpandedRenderLists={{}} setMobileExpandedRenderLists={() => {}}
    newEstimateItem={{sectionId: '', name: ''}} setNewEstimateItem={() => {}}
    estimateIssueFocusKey=""
  /></>;
}

beforeEach(() => {
  fetchFn = jest.fn();
  qualityReview = jest.fn().mockResolvedValue(undefined);
  normReview = jest.fn().mockResolvedValue(undefined);
  saves = [];
  jest.spyOn(window, 'alert').mockImplementation(() => {});
});
afterEach(() => jest.restoreAllMocks());

function openEditor() {
  const view = render(<Harness />);
  act(() => { state.setSelectedEstimate(a); state.setEstimatesList([a, b]); });
  return view;
}
function editName(previous, next) {
  fireEvent.change(screen.getByDisplayValue(previous), {target: {value: next}});
}
function saveOnBlur(name) {
  fireEvent.blur(screen.getByDisplayValue(name));
  const index = saves.length - 1;
  expect(fetchFn.mock.calls[index][0]).toBe('/api/estimates/7');
  const request = fetchFn.mock.calls[index][1];
  expect(request.method).toBe('PUT');
  expect(JSON.parse(request.body)).toEqual({...state.selectedEstimate, expectedRevision: state.selectedEstimate.revision});
  return saves[index];
}
function snapshot(view) {
  return {
    // Compare all existing application state, not invented dirty/status/error flags.
    appState: {...state}, selection: {...state.estimateSelectionRef.current},
    editor: state.selectedEstimate, list: state.estimatesList, html: view.container.innerHTML,
  };
}
function expectUnchanged(view, before) {
  expect(state).toEqual(before.appState);
  expect(state.estimateSelectionRef.current).toEqual(before.selection);
  expect(state.selectedEstimate).toBe(before.editor);
  expect(state.estimatesList).toBe(before.list);
  expect(view.container.innerHTML).toBe(before.html);
  expect(window.alert).not.toHaveBeenCalled();
}
async function settle(response, outcome, saving) {
  await act(async () => {
    if (outcome === 'network-error') response.reject(new Error('offline'));
    else response.resolve({ok: outcome === 'success', status: outcome === 'success' ? 200 : outcome === 'conflict' ? 409 : 500, json: async () => outcome === 'success' ? {ok: true, revision: 2} : {detail: {code: outcome === 'conflict' ? 'estimate_revision_conflict' : 'failed', currentRevision: 2}}});
    await saving;
  });
}

const staleCases = ['edit', 'switch', 'close', 'reopen']
  .flatMap(scenario => outcomes.map(outcome => [scenario, outcome]));
test.each(staleCases)('ordinary save → %s → late %s leaves editor state unchanged', async (scenario, outcome) => {
  const response = deferred();
  fetchFn.mockReturnValueOnce(response.promise);
  const view = openEditor();
  editName('Работа 7', 'Сохранённая правка');
  const saving = saveOnBlur('Сохранённая правка');
  const savedDraft = state.selectedEstimate;
  if (scenario === 'edit') editName('Сохранённая правка', 'Новая несохранённая правка');
  act(() => {
    if (scenario === 'switch') state.setSelectedEstimate(b);
    if (scenario === 'close' || scenario === 'reopen') state.setSelectedEstimate(null);
    if (scenario === 'reopen') state.setSelectedEstimate(savedDraft);
  });
  const before = snapshot(view);
  await settle(response, outcome, saving);
  expectUnchanged(view, before);
  expect(qualityReview).not.toHaveBeenCalled();
  expect(normReview).not.toHaveBeenCalled();
  const expectedNames = {edit: 'Новая несохранённая правка', switch: 'Работа 8', close: null, reopen: 'Сохранённая правка'};
  expect(state.selectedEstimate?.sections[0].items[0].name ?? null).toBe(expectedNames[scenario]);
});

const reversedCases = outcomes.flatMap(older => outcomes.map(newer => [older, newer]));
test.each(reversedCases)('two saves resolve newest first (%s older, %s newer) without changing UI state', async (olderOutcome, newerOutcome) => {
  const older = deferred(), newer = deferred();
  fetchFn.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
  const view = openEditor();
  editName('Работа 7', 'Первая правка');
  const first = saveOnBlur('Первая правка');
  editName('Первая правка', 'Вторая правка');
  const second = saveOnBlur('Вторая правка');
  expect(fetchFn).toHaveBeenCalledTimes(2);
  expect(JSON.parse(fetchFn.mock.calls[0][1].body).sections[0].items[0].name).toBe('Первая правка');
  expect(JSON.parse(fetchFn.mock.calls[1][1].body).sections[0].items[0].name).toBe('Вторая правка');
  await settle(newer, newerOutcome, second);
  expect(state.estimateSaveState.status).toBe(newerOutcome === 'success' ? 'saved' : newerOutcome === 'conflict' ? 'conflict' : 'error');
  const before = snapshot(view);
  await settle(older, olderOutcome, first);
  expectUnchanged(view, before);
  expect(screen.getByDisplayValue('Вторая правка')).toBeInTheDocument();
  expect(qualityReview).toHaveBeenCalledTimes(newerOutcome === 'success' ? 1 : 0);
  expect(normReview).toHaveBeenCalledTimes(newerOutcome === 'success' ? 1 : 0);
});

 test('conflict preserves local edits and old server revision without retry', async () => {
  const response = deferred();
  fetchFn.mockReturnValueOnce(response.promise);
  openEditor();
  editName('Работа 7', 'Мои локальные правки');
  const saving = saveOnBlur('Мои локальные правки');
  const draft = state.selectedEstimate;
  await settle(response, 'conflict', saving);
  expect(state.selectedEstimate).toBe(draft);
  expect(state.selectedEstimate.revision).toBe(1);
  expect(screen.getByRole('alert')).toHaveTextContent('Смета изменена на сервере');
  expect(screen.getByDisplayValue('Мои локальные правки')).toBeInTheDocument();
  expect(fetchFn).toHaveBeenCalledTimes(1);
  expect(qualityReview).not.toHaveBeenCalled();
  expect(normReview).not.toHaveBeenCalled();
});

test('next explicit save uses the acknowledged revision', async () => {
  const first = deferred(), second = deferred();
  fetchFn.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  openEditor();
  editName('Работа 7', 'Первая правка');
  const saving = saveOnBlur('Первая правка');
  await settle(first, 'success', saving);
  expect(state.selectedEstimate.revision).toBe(2);
  editName('Первая правка', 'Вторая правка');
  const nextSaving = saveOnBlur('Вторая правка');
  expect(JSON.parse(fetchFn.mock.calls[1][1].body).expectedRevision).toBe(2);
  await act(async () => { second.resolve({ok:true,json:async()=>({revision:3})}); await nextSaving; });
  expect(state.selectedEstimate.revision).toBe(3);
  expect(state.estimateSaveState.status).toBe('saved');
});

test('an edit during quality review prevents the subsequent norm review', async () => {
  const response = deferred(), review = deferred();
  fetchFn.mockReturnValueOnce(response.promise);
  qualityReview.mockReturnValueOnce(review.promise);
  openEditor();
  const saving = saveOnBlur('Работа 7');
  await act(async () => { response.resolve({ok:true,json:async()=>({revision:2})}); });
  expect(qualityReview).toHaveBeenCalledTimes(1);
  editName('Работа 7', 'Новая правка');
  await act(async () => { review.resolve(); await saving; });
  expect(normReview).not.toHaveBeenCalled();
  expect(state.estimateSaveState.status).toBe('dirty');
});
