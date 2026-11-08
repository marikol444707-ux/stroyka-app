import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import AppWorkflowModals from './AppWorkflowModals';
import { buildAppShellProps } from '../features/app-shell/buildAppShellProps';
import { useAppMainState } from '../features/app-shell/useAppMainState';

const original = {id: 7, revision: 1, name: 'Смета', sections: [{name: 'Исходная', items: []}]};
const restored = [{name: 'Восстановленная', items: []}];
const deferred = () => {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return {promise, resolve};
};
let state;
const closeHistory = jest.fn();
function Harness() {
  state = useAppMainState();
  const props = buildAppShellProps({
    appMainState: state, API: '/api', user: {name: 'Тест'}, ui: {C: {}},
    estimateWorkflowState: {
      showVersionHistory: true, setShowVersionHistory: closeHistory,
      estimateVersions: [{id: 3, versionLabel: '1'}], selectedVersionsToCompare: [],
    },
  });
  return <AppWorkflowModals {...props.appWorkflowModalsProps} />;
}
beforeEach(() => {
  closeHistory.mockClear();
  jest.spyOn(window, 'confirm').mockReturnValue(true);
  jest.spyOn(window, 'alert').mockImplementation(() => {});
});
afterEach(() => { jest.restoreAllMocks(); delete global.fetch; });

async function startRestore() {
  const save = deferred();
  global.fetch = jest.fn().mockResolvedValueOnce({json: async () => ({sections: restored})})
    .mockReturnValueOnce(save.promise);
  render(<Harness />);
  act(() => { state.setSelectedEstimate(original); state.setEstimatesList([original]); });
  const restoreButton = await screen.findByText('↶ Восстановить');
  await act(async () => { fireEvent.click(restoreButton); });
  expect(fetch).toHaveBeenCalledTimes(2);
  return save;
}

test.each(['edit', 'switch', 'close', 'reopen'])('late restore save preserves current state after %s', async scenario => {
  const save = await startRestore();
  act(() => {
    if (scenario === 'edit') state.setSelectedEstimate({...original, name: 'Новая правка'});
    if (scenario === 'switch') state.setSelectedEstimate({id: 8, name: 'Другая', sections: []});
    if (scenario === 'close' || scenario === 'reopen') state.setSelectedEstimate(null);
    if (scenario === 'reopen') state.setSelectedEstimate(original);
  });
  const expected = state.selectedEstimate;
  await act(async () => { save.resolve({ok: true, json: async () => ({revision: 2})}); });
  expect(state.selectedEstimate).toBe(expected);
  expect(state.estimatesList).toEqual([original]);
  expect(closeHistory).not.toHaveBeenCalled();
  expect(window.alert).not.toHaveBeenCalled();
});

test('successful current restore applies saved sections', async () => {
  const save = await startRestore();
  await act(async () => { save.resolve({ok: true, json: async () => ({revision: 2})}); });
  expect(state.selectedEstimate.sections).toEqual(restored);
  expect(state.estimatesList[0].sections).toEqual(restored);
  expect(closeHistory).toHaveBeenCalledWith(false);
});

test('failed save does not apply restored sections', async () => {
  const save = await startRestore();
  await act(async () => { save.resolve({ok: false, json: async () => ({detail: "Ошибка сохранения"})}); });
  expect(state.selectedEstimate).toBe(original);
  expect(state.estimatesList).toEqual([original]);
  expect(closeHistory).not.toHaveBeenCalled();
});

test.each(['edit', 'switch', 'close', 'reopen'])('late version download does not start a save after %s', async scenario => {
  const version = deferred();
  global.fetch = jest.fn().mockReturnValueOnce(version.promise);
  render(<Harness />);
  act(() => { state.setSelectedEstimate(original); state.setEstimatesList([original]); });
  fireEvent.click(await screen.findByText('↶ Восстановить'));
  act(() => {
    if (scenario === 'edit') state.setSelectedEstimate({...original, name: 'Новая правка'});
    if (scenario === 'switch') state.setSelectedEstimate({id: 8});
    if (scenario === 'close' || scenario === 'reopen') state.setSelectedEstimate(null);
    if (scenario === 'reopen') state.setSelectedEstimate(original);
  });
  const expected = state.selectedEstimate;
  await act(async () => { version.resolve({json: async () => ({sections: restored})}); });
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(state.selectedEstimate).toBe(expected);
  expect(state.estimatesList).toEqual([original]);
  expect(closeHistory).not.toHaveBeenCalled();
});

test('connection failure keeps the current draft and history open', async () => {
  const save = await startRestore();
  await act(async () => { save.resolve(Promise.reject(new Error('offline'))); });
  expect(state.selectedEstimate).toBe(original);
  expect(state.estimatesList).toEqual([original]);
  expect(closeHistory).not.toHaveBeenCalled();
  expect(screen.getByRole('alert')).toHaveTextContent('offline');
});

 test('restoring a version sends the expected revision and preserves the draft on conflict', async () => {
  const save = await startRestore();
  expect(JSON.parse(fetch.mock.calls[1][1].body).expectedRevision).toBe(1);
  await act(async () => { save.resolve({ok:false,status:409,json:async()=>({detail:{code:'estimate_revision_conflict',currentRevision:2}})}); });
  expect(state.selectedEstimate).toBe(original);
  expect(state.selectedEstimate.revision).toBe(1);
  expect(closeHistory).not.toHaveBeenCalled();
  expect(screen.getByRole('alert')).toHaveTextContent('Смета изменена на сервере');
  expect(fetch).toHaveBeenCalledTimes(2);
});
