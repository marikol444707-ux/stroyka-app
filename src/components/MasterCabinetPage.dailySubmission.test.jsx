import React from 'react';
import {act, fireEvent, render, screen, waitFor} from '@testing-library/react';

import {ESTIMATE_CONFLICT_MESSAGE} from '../features/estimates/estimateSaveClient';
import MasterCabinetPage from './MasterCabinetPage';
import {normalizeEstimateList} from '../utils/estimateUtils';

const API = '/api';
const PHOTO = '/uploads/daily-report.png';
const CONFLICT = 'Смета изменена другим сотрудником. Обновите данные и повторите отправку.';
const estimate = {
  id: 51, revision: 3, name: 'Смета', projectName: 'Тестовый объект',
  workPackage: 'Основная', status: 'Активная',
  sections: [{name: 'Отделка', items: [{
    estimateItemKey: 'paint-51', name: 'Покраска стен', unit: 'м2',
    quantity: 20, doneQuantity: 2, priceWork: 500,
  }]}],
};
// A supplied contract line is fixture input; this suite does not create assignments.
const contractItem = {
  id: 81, contractId: 71, projectName: estimate.projectName,
  workPackage: 'Основная', estimateItemKey: 'paint-51', name: 'Покраска стен',
  unit: 'м2', quantity: 20, doneQuantity: 2, priceBrigade: 200,
};
const freshEstimate = {
  ...estimate, revision: 17,
  sections: [{...estimate.sections[0], items: [{...estimate.sections[0].items[0], doneQuantity: 4}]}],
};
const response = (body, status = 200) => ({ok: status < 400, status, json: async () => body});

function renderCabinet(estimatesList = [estimate], brigadeContractItems = [contractItem]) {
  const notify = jest.fn();
  const refreshData = jest.fn().mockResolvedValue(undefined);
  const appendPhotos = jest.fn().mockResolvedValue(PHOTO);
  function Harness() {
    const [estimateDoneDrafts, setEstimateDoneDrafts] = React.useState({});
    const [estimateWorkParams, setEstimateWorkParams] = React.useState({});
    const [estimateWorkMaterials, setEstimateWorkMaterials] = React.useState({});
    return <MasterCabinetPage
      API={API} activePage="works" C={{}} ROLE_LABELS={{}} SURFACES={['Стены']}
      user={{id: 9, name: 'Мастер', role: 'мастер'}} companyContext={{selectedCompanyId: 3}}
      projects={[{id: 11, name: estimate.projectName}]} masterProjectId="11"
      estimatesList={estimatesList} brigadeContractItems={brigadeContractItems}
      contracts={[]} brigadeContracts={[]} piecework={[]} materialTransfers={[]}
      pricelistItems={[]} interimActs={[]} rooms={[]} tools={[]} workJournal={[]}
      selectedWorks={{}} notifications={[]} unreadNotifications={0}
      estimateWorkKey={(id, section, item) => `${id}:${section}:${item}`}
      estimateDoneDrafts={estimateDoneDrafts} setEstimateDoneDrafts={setEstimateDoneDrafts}
      estimateWorkParams={estimateWorkParams} setEstimateWorkParams={setEstimateWorkParams}
      estimateWorkMaterials={estimateWorkMaterials} setEstimateWorkMaterials={setEstimateWorkMaterials}
      prepareWorkMaterialGroups={(_project, groups) => groups}
      renderMaterialWriteoffStatus={() => null}
      appendPhotos={appendPhotos} fileSrc={value => value}
      notify={notify} refreshData={refreshData}
    />;
  }
  render(<Harness/>);
  return {notify, refreshData, appendPhotos};
}

async function prepareDay() {
  const quantity = screen.getByPlaceholderText('сегодня, м2');
  fireEvent.change(quantity, {target: {value: '3'}});
  fireEvent.blur(quantity);
  fireEvent.click(screen.getByRole('button', {name: 'Сформировать работы в один акт'}));
  expect(screen.getByRole('heading', {name: 'Работы за день'})).toBeInTheDocument();
  fireEvent.change(screen.getByPlaceholderText('Комментарий прорабу или директору'), {
    target: {value: 'Покрашено сегодня'},
  });
  const photoField = screen.getByText('Общий фотоотчет').parentElement.parentElement;
  fireEvent.change(photoField.querySelector('input[multiple]'), {
    target: {files: [new File(['photo'], 'daily-report.png', {type: 'image/png'})]},
  });
  expect(await screen.findByRole('img', {name: 'Прикрепленное фото'})).toHaveAttribute('src', PHOTO);
}

const putCalls = () => global.fetch.mock.calls.filter(([, options]) => options?.method === 'PUT');

describe.each([['legacy', '0'], ['material accounting v2', '1']])('daily submission: %s', (_label, flag) => {
  const originalFetch = global.fetch;
  const originalFlag = process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
  const originalCrypto = Object.getOwnPropertyDescriptor(window, 'crypto');

  beforeEach(() => {
    process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = flag;
    sessionStorage.clear();
    Object.defineProperty(window, 'crypto', {configurable: true, value: require('crypto').webcrypto});
    global.fetch = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalFlag === undefined) delete process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
    else process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = originalFlag;
    if (originalCrypto) Object.defineProperty(window, 'crypto', originalCrypto);
    else delete window.crypto;
    sessionStorage.clear();
  });

  test('sends the exact fresh revision and adds the daily quantity to fresh progress', async () => {
    global.fetch.mockImplementation(async (url, options) => {
      if (url !== API + '/estimates/51') throw new Error('Unexpected request: ' + url);
      return options?.method === 'PUT' ? response({...freshEstimate, revision: 18, ok: true}) : response(freshEstimate);
    });
    const {notify, refreshData} = renderCabinet();
    await prepareDay();
    fireEvent.click(screen.getByRole('button', {name: 'Отправить на проверку'}));
    await waitFor(() => expect(notify).toHaveBeenCalledTimes(1));
    expect(putCalls()).toHaveLength(1);
    const payload = JSON.parse(putCalls()[0][1].body);
    expect(payload.sections[0].items[0].doneQuantity).toBe(7);
    expect(payload._workJournalParams['paint-51']).toMatchObject({
      photoUrl: PHOTO, contractItemId: 81, executionTotal: 600,
    });
    expect(refreshData).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('heading', {name: 'Работы за день'})).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText('сегодня, м2')).toHaveValue(null);
    expect(payload.expectedRevision).toBe(freshEstimate.revision);
  });

  test('preserves quantity, photo and comment on HTTP 409 and shows detail.message without success effects', async () => {
    global.fetch.mockImplementation(async (url, options) => {
      if (url !== API + '/estimates/51') throw new Error('Unexpected request: ' + url);
      return options?.method === 'PUT'
        ? response({detail: {code: 'estimate_revision_conflict', message: CONFLICT}}, 409)
        : response(freshEstimate);
    });
    const {notify, refreshData} = renderCabinet();
    await prepareDay();
    fireEvent.click(screen.getByRole('button', {name: 'Отправить на проверку'}));
    await waitFor(() => expect(screen.getByRole('button', {name: 'Отправить на проверку'})).toBeEnabled());
    expect(putCalls()).toHaveLength(1);
    expect(screen.getByRole('heading', {name: 'Работы за день'})).toBeInTheDocument();
    expect(screen.getByPlaceholderText('сегодня, м2')).toHaveValue(3);
    expect(screen.getByRole('img', {name: 'Прикрепленное фото'})).toHaveAttribute('src', PHOTO);
    expect(screen.getByPlaceholderText('Комментарий прорабу или директору')).toHaveValue('Покрашено сегодня');
    expect(notify).not.toHaveBeenCalled();
    expect(refreshData).not.toHaveBeenCalled();
    expect(screen.getAllByText('Не удалось отправить дневной пакет: ' + (flag === '0' ? ESTIMATE_CONFLICT_MESSAGE : CONFLICT)).length).toBeGreaterThan(0);
  });

  test('disables submission while the fresh GET is pending and ignores a second click', async () => {
    let resolveFresh;
    const fresh = new Promise(resolve => { resolveFresh = resolve; });
    global.fetch.mockImplementation((url, options) => {
      if (url !== API + '/estimates/51') throw new Error('Unexpected request: ' + url);
      return options?.method === 'PUT' ? Promise.resolve(response({...freshEstimate, revision: 18, ok: true})) : fresh;
    });
    const {notify} = renderCabinet();
    await prepareDay();
    const submit = screen.getByRole('button', {name: 'Отправить на проверку'});
    fireEvent.click(submit);
    expect(submit).toBeDisabled();
    fireEvent.click(submit);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    await act(async () => { resolveFresh(response(freshEstimate)); });
    await waitFor(() => expect(notify).toHaveBeenCalledTimes(1));
    expect(putCalls()).toHaveLength(1);
  });
});

test('keeps an existing contracted estimate row visible after list normalization generates a workKey', () => {
  const normalized = normalizeEstimateList([{
    ...estimate,
    sections: [{name: 'Отделка', items: [{
      ...estimate.sections[0].items[0], estimateItemKey: undefined, id: 'paint-51',
    }]}],
  }]);
  const normalizedItem = normalized[0].sections[0].items[0];
  expect(normalizedItem.id).toBe(contractItem.estimateItemKey);
  expect(normalizedItem.workKey).toBeTruthy();
  expect(normalizedItem.workKey).not.toBe(contractItem.estimateItemKey);
  renderCabinet(normalized);
  expect(screen.getByPlaceholderText('сегодня, м2')).toBeInTheDocument();
});
