import React, { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ProjectWorkJournalPanel from '../../components/ProjectWorkJournalPanel';
import MasterHistoryPage from '../../components/MasterHistoryPage';
import WorkAcceptancePanel from './WorkAcceptancePanel';
import { createMaterialWriteoffActions } from '../material-writeoff/materialWriteoffActions';
import { pendingWorkBatch } from '../work-material-accounting/workCommands';

jest.mock('../uploads/useProtectedFileObjectUrl', () => () => ({ src: 'blob:synthetic-work-photo' }));

const context = { mode: 'company', selectedCompanyId: 2 };
const worker = { id: 9, role: 'мастер', name: 'Мастер' };
const C = { text: '#000', bg: '#fff', card: '#fff', border: '#ccc', warning: '#f90', inp: {} };
const baseView = { journalId: 11, status: 'На проверке', quantity: 100, unit: 'м²', projectId: 7,
  description: 'Штукатурка стен', project: 'Лицей', masterName: 'Мастер', roomName: 'Класс', date: '2026-09-18',
  workPackage: 'Основная', photos: [], expectedState: 'state-1', history: [], canReview: true,
  canResubmit: false, parentJournalId: null, reworkJournalId: null };
const reworkView = { ...baseView, journalId: 12, status: 'На доработке', quantity: 40,
  canReview: false, canResubmit: true, parentJournalId: 11, expectedState: 'child-state',
  returnReason: 'Исправить углы' };
const stock = { cement: { name: 'Цемент', unit: 'кг', workPackage: 'Основная', quantity: 3,
  personalAvailable: 1, warehouseAvailable: 2, warehouseMaterialId: 41,
  sourceConflict: false, materialAccountingVersion: 2 } };
const available = () => stock;
const prepare = createMaterialWriteoffActions({
  materialAvailabilityMapForWork: available, canonicalMaterialMeta: (_project, name, unit) => ({ name, unit }),
  materialNameKey: () => 'cement', isPersonalMaterialRole: true, fmtMeasure: (q, unit) => `${q} ${unit}`,
}).prepareWorkMaterialGroups;

let oldFetch, oldFlags;
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  Object.defineProperty(window, 'crypto', { configurable: true, value: require('crypto').webcrypto });
});
beforeEach(() => {
  oldFetch = global.fetch;
  oldFlags = [process.env.REACT_APP_WORK_ACCEPTANCE_ENABLED, process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED];
  process.env.REACT_APP_WORK_ACCEPTANCE_ENABLED = '1';
  process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = '1';
  sessionStorage.clear();
});
afterEach(() => {
  global.fetch = oldFetch;
  ['REACT_APP_WORK_ACCEPTANCE_ENABLED', 'REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED'].forEach((key, i) => {
    if (oldFlags[i] === undefined) delete process.env[key]; else process.env[key] = oldFlags[i];
  });
});

test('foreman enters the lifecycle from project journal and opens the exact partial remainder', async () => {
  const edits = jest.fn(), legacyConfirm = jest.fn(), legacyReject = jest.fn(), refreshed = jest.fn();
  const commands = [];
  let parent = { ...baseView };
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      commands.push({ url, payload: JSON.parse(options.body) });
      parent = { ...parent, quantity: 60, status: 'Подтверждено', canReview: false, reworkJournalId: 12,
        history: [{ id: 1, decision: 'accept', acceptedQuantity: 60, submittedQuantity: 100,
          actorName: 'Прораб', createdAt: '2026-09-18T12:00:00Z', reason: 'Исправить углы', photos: [] }] };
      return { ok: true, json: async () => ({ ok: true, journalId: 11, reviewId: 1, reworkJournalId: 12 }) };
    }
    return { ok: true, json: async () => url.endsWith('/12/acceptance')
      ? { ...reworkView, canResubmit: false } : parent };
  });
  render(<ProjectWorkJournalPanel API="/api" companyContext={context} user={{ id: 3, role: 'прораб' }}
    onChanged={refreshed} project={{ id: 7, name: 'Лицей' }}
    workJournal={[{ ...baseView, id: 11, materialAccountingVersion: 2, masterId: 9 }]}
    canConfirm matchSearch={() => true} setListSearch={jest.fn()} setEditingJournal={edits}
    openConfirmModal={legacyConfirm} setRejectingEntry={legacyReject} getActStatusForJournal={() => null}
    C={C} inp={{}} btnB={{}} btnG={{}} btnGr={{}} btnR={{}} badge={() => ({})} />);
  fireEvent.click(screen.getByRole('button', { name: 'Проверить работу' }));
  fireEvent.change(await screen.findByLabelText('Принять (м²)'), { target: { value: '60' } });
  fireEvent.change(screen.getByLabelText('Замечания'), { target: { value: 'Исправить углы' } });
  fireEvent.click(screen.getByRole('button', { name: 'Принять объём' }));
  await waitFor(() => expect(refreshed).toHaveBeenCalledTimes(1));
  expect(commands).toHaveLength(1);
  expect(commands[0]).toMatchObject({ url: '/api/work-journal/11/acceptance', payload: {
    expectedState: 'state-1', acceptedQuantity: '60', decision: 'accept', reason: 'Исправить углы',
    expectedCompanyId: 2, expectedActorId: 3,
  } });
  expect(edits).not.toHaveBeenCalled(); expect(legacyConfirm).not.toHaveBeenCalled(); expect(legacyReject).not.toHaveBeenCalled();
  fireEvent.click(await screen.findByRole('button', { name: 'Доработка №12' }));
  await screen.findByText('Замечания к доработке:');
  expect(screen.getByText('Исправить углы')).toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledWith('/api/work-journal/12/acceptance', expect.objectContaining({
    headers: { 'X-Company-Mode': 'company', 'X-Company-Id': '2' }, credentials: 'include',
  }));
});

function HistoryHarness() {
  const [selected, setSelected] = useState(null);
  return <>
    <MasterHistoryPage C={C} btnG={{}} card={{}} expandedProject="2026-09-18" fileSrc={value => value}
      fmtMeasure={(q, unit) => `${q} ${unit}`} listSearch="" matchSearch={() => true}
      myJournal={[{ ...reworkView, id: 12, materialAccountingVersion: 2, masterId: 9 }]}
      piecework={[]} setExpandedProject={jest.fn()} setListSearch={jest.fn()} setShowPhotoModal={jest.fn()}
      sumConfirmed={0} user={worker} onOpenAcceptance={setSelected} />
    {selected && <WorkAcceptancePanel journal={selected} API="/api" companyContext={context} user={worker}
      C={C} onClose={() => setSelected(null)} onChanged={jest.fn()}
      materialAvailabilityMapForWork={available} prepareWorkMaterialGroups={prepare} />}
  </>;
}

test('master history resubmits additional mixed consumption and lost-reply recovery repeats the identical command', async () => {
  const posts = [];
  let view = { ...reworkView }, dropped = false;
  global.fetch = jest.fn(async (url, options = {}) => {
    if (url.endsWith('/upload-photo')) return { ok: true, json: async () => ({ contentUrl: '/tenant-files/77/content' }) };
    if (options.method === 'POST') {
      posts.push({ url, headers: options.headers, payload: JSON.parse(options.body) });
      view = { ...view, status: 'На проверке', canResubmit: false, comment: 'Углы исправлены', photos: ['/tenant-files/77/content'] };
      if (!dropped) { dropped = true; throw new Error('Failed to fetch'); }
      return { ok: true, json: async () => ({ ok: true, journalId: 12 }) };
    }
    return { ok: true, json: async () => view };
  });
  render(<HistoryHarness />);
  fireEvent.click(screen.getByRole('button', { name: 'Исправить и сдать' }));
  fireEvent.change(await screen.findByLabelText('Что исправлено'), { target: { value: 'Углы исправлены' } });
  fireEvent.change(screen.getByLabelText('Добавить материал'), { target: { value: '0' } });
  fireEvent.change(screen.getByLabelText('Расход (кг)'), { target: { value: '2' } });
  expect(screen.getByText('С остатка мастера: 1 кг. Со склада: 1 кг.')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Новые фотографии'), {
    target: { files: [new File(['photo'], 'rework.jpg', { type: 'image/jpeg' })] },
  });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Сдать доработку' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Сдать доработку' }));
  await screen.findByText(/Связь прервалась/);
  expect(posts).toHaveLength(1);
  expect(posts[0]).toMatchObject({ url: '/api/work-journal/12/resubmit', payload: {
    expectedState: 'child-state', comment: 'Углы исправлены', photos: ['/tenant-files/77/content'],
    expectedCompanyId: 2, expectedActorId: 9,
    materialsUsed: [{ name: 'Цемент', quantity: '2', workPackage: 'Основная', personalQuantity: 1,
      warehouseQuantity: 1, warehouseMaterialId: 41, materialAccountingVersion: 2 }],
  } });
  expect(posts[0].payload).not.toHaveProperty('quantity');
  expect(pendingWorkBatch({ companyId: 2, userId: 9 }).next).toBe(0);
  fireEvent.click(screen.getByRole('button', { name: 'Повторить сохранённую отправку' }));
  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[1]).toEqual(posts[0]);
  await waitFor(() => expect(pendingWorkBatch({ companyId: 2, userId: 9 })).toBeNull());
  expect(screen.queryByRole('button', { name: 'Сдать доработку' })).not.toBeInTheDocument();
});

test('changing authenticated worker in the same company reloads scope and removes the previous worker draft', async () => {
  let actor = worker.id;
  global.fetch = jest.fn(async () => actor === worker.id
    ? { ok: true, json: async () => ({ ...reworkView }) }
    : { ok: false, status: 404, json: async () => ({ detail: 'Работа не назначена исполнителю' }) });
  const props = { journal: { id: 12 }, API: '/api', companyContext: context, user: worker, C,
    onClose: jest.fn(), onChanged: jest.fn(), materialAvailabilityMapForWork: available, prepareWorkMaterialGroups: prepare };
  const { rerender } = render(<WorkAcceptancePanel {...props} />);
  fireEvent.change(await screen.findByLabelText('Что исправлено'), { target: { value: 'Private draft of previous worker' } });
  actor = 19;
  rerender(<WorkAcceptancePanel {...props} user={{ id: 19, role: 'мастер', name: 'Другой мастер' }} />);
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  expect(await screen.findByText(/Работа не назначена исполнителю/)).toBeInTheDocument();
  expect(screen.queryByDisplayValue('Private draft of previous worker')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Что исправлено')).not.toBeInTheDocument();
});
