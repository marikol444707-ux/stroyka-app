import React from 'react';
import {cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';

import CustomerCabinetPage from './CustomerCabinetPage';
import SupervisorCabinetPage from './SupervisorCabinetPage';

const project = {id: 41, companyId: 3, name: 'Объект', status: 'В работе'};
const journal = [{
  id: 19, companyId: 3, projectId: 41, project: 'Объект', masterId: 11, masterName: 'Мастер',
  description: 'Принятая покраска стен', quantity: 3, unit: 'м2', status: 'Подтверждено',
  date: new Date().toISOString().split('T')[0],
  photoUrl: '/tenant-files/5/content, /tenant-files/6/content',
}];

function renderCabinet(kind) {
  const setShowPhotoModal = jest.fn();
  const shared = {
    C: {}, projects: [project], workJournal: journal,
    user: {id: 21, name: 'Наблюдатель', role: kind, companyId: 3, projectId: 41},
    companyContext: {mode: 'company', selectedCompanyId: 3, companies: [{companyId: 3, role: kind}]},
    listSearch: '', matchSearch: () => true, computeNotifications: () => [],
    fmtMeasure: (quantity, unit) => `${quantity} ${unit}`,
    fileSrc: value => '/api' + value, setShowPhotoModal,
    projectRealProgress: () => 0, projectPlanDone: () => ({done: 0, plan: 0}),
    checklists: [], prescriptionsList: [], supervisorActs: [], materialInspections: [],
    hiddenActs: [], projectStages: [], unexpectedWorksList: [], projectPayments: [],
  };
  const Component = kind === 'технадзор' ? SupervisorCabinetPage : CustomerCabinetPage;
  return {...render(<Component {...shared}/>), setShowPhotoModal};
}

async function acceptedWorkCard(kind) {
  const title = kind === 'технадзор'
    ? '👷 Принятые работы (последние 30 дней)'
    : '👷 Что выполнено по объекту (последние 30 дней)';
  const header = await screen.findByText(title);
  const card = header.parentElement.parentElement;
  expect(within(card).getByText('Принятая покраска стен')).toBeVisible();
  return card;
}

describe('accepted master work photos in customer and supervisor cabinets', () => {
  const originalFetch = global.fetch;
  const originalCreateObjectURL = URL.createObjectURL;
  const originalRevokeObjectURL = URL.revokeObjectURL;
  let rejectPhotos;

  beforeEach(() => {
    rejectPhotos = false;
    const photoOne = new Blob(['first'], {type: 'image/png'});
    const photoTwo = new Blob(['second'], {type: 'image/png'});
    URL.createObjectURL = jest.fn(blob => blob === photoOne ? 'blob:work-one' : 'blob:work-two');
    URL.revokeObjectURL = jest.fn();
    global.fetch = jest.fn(async url => {
      if (url.endsWith('/estimates')) return {ok: true, json: async () => []};
      if (url.includes('/work-journal?')) return {ok: true, json: async () => journal};
      if (url === '/api/tenant-files/5/content' || url === '/api/tenant-files/6/content') {
        return rejectPhotos ? {ok: false, status: 403}
          : {ok: true, blob: async () => url.endsWith('/5/content') ? photoOne : photoTwo};
      }
      throw new Error('Unexpected request: ' + url);
    });
  });

  afterEach(() => {
    cleanup();
    global.fetch = originalFetch;
    if (originalCreateObjectURL) URL.createObjectURL = originalCreateObjectURL;
    else delete URL.createObjectURL;
    if (originalRevokeObjectURL) URL.revokeObjectURL = originalRevokeObjectURL;
    else delete URL.revokeObjectURL;
  });

  test.each(['технадзор', 'заказчик'])('%s opens both accepted-work CSV photos as authenticated blobs', async kind => {
    const {container, unmount, setShowPhotoModal} = renderCabinet(kind);
    const card = await acceptedWorkCard(kind);
    const first = await within(card).findByRole('button', {name: 'Фото работы 1'});
    const second = await within(card).findByRole('button', {name: 'Фото работы 2'});
    await waitFor(() => { expect(first).toBeEnabled(); expect(second).toBeEnabled(); });
    fireEvent.click(first);
    fireEvent.click(second);
    expect(setShowPhotoModal.mock.calls).toEqual([['blob:work-one'], ['blob:work-two']]);
    for (const id of [5, 6]) {
      expect(global.fetch).toHaveBeenCalledWith(`/api/tenant-files/${id}/content`,
        expect.objectContaining({credentials: 'include', cache: 'no-store'}));
    }
    expect(container.querySelector('[src*="tenant-files"], [href*="tenant-files"]')).toBeNull();
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:work-one');
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:work-two');
  });

  test('customer photo gallery splits the same accepted-work CSV into two usable previews', async () => {
    const {setShowPhotoModal} = renderCabinet('заказчик');
    await acceptedWorkCard('заказчик');
    const gallery = screen.getByText('📷 Фото-отчёт').parentElement;
    const first = await within(gallery).findByRole('img', {name: 'Фото работы 1'});
    const second = await within(gallery).findByRole('img', {name: 'Фото работы 2'});
    expect(first).toHaveAttribute('src', 'blob:work-one');
    expect(second).toHaveAttribute('src', 'blob:work-two');
    fireEvent.click(first);
    fireEvent.click(second);
    expect(setShowPhotoModal.mock.calls).toEqual([['blob:work-one'], ['blob:work-two']]);
    for (const id of [5, 6]) {
      expect(global.fetch).toHaveBeenCalledWith(`/api/tenant-files/${id}/content`,
        expect.objectContaining({credentials: 'include', cache: 'no-store'}));
    }
  });

  test.each(['технадзор', 'заказчик'])('%s reports a protected-photo denial without a raw URL fallback', async kind => {
    rejectPhotos = true;
    const {container, setShowPhotoModal} = renderCabinet(kind);
    const card = await acceptedWorkCard(kind);
    expect((await within(card).findAllByRole('alert')).length).toBeGreaterThan(0);
    expect(global.fetch).toHaveBeenCalledWith('/api/tenant-files/5/content',
      expect.objectContaining({credentials: 'include', cache: 'no-store'}));
    expect(container.querySelector('[src*="tenant-files"], [href*="tenant-files"]')).toBeNull();
    expect(setShowPhotoModal).not.toHaveBeenCalled();
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });
});
