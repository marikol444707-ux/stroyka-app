import React, { useEffect, useState } from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import ProjectCableJournalEditModal from './ProjectCableJournalEditModal';
import ProjectMaterialInspectionEditModal from './ProjectMaterialInspectionEditModal';
import MasterCablePage from './MasterCablePage';
import { qualityJournalScopeKey } from '../utils/qualityJournalScope';
import { getQualityJournalRevision, getQualityJournalMutationState, QUALITY_JOURNAL_MUTATED } from '../utils/qualityJournalEvents';

// Isolate sticky uncertainty between scenarios while exercising the real token API.
jest.mock('../utils/qualityJournalEvents', () => {
  let api = jest.requireActual('../utils/qualityJournalEvents');
  return {
    QUALITY_JOURNAL_MUTATED: api.QUALITY_JOURNAL_MUTATED,
    getQualityJournalRevision: () => api.getQualityJournalRevision(),
    getQualityJournalMutationState: () => api.getQualityJournalMutationState(),
    qualityJournalMutationIssue: () => api.qualityJournalMutationIssue(),
    beginQualityJournalMutation: () => api.beginQualityJournalMutation(),
    finishQualityJournalMutation: (...args) => api.finishQualityJournalMutation(...args),
    resetTestState: () => { jest.isolateModules(() => { api = jest.requireActual('../utils/qualityJournalEvents'); }); },
  };
});

const cable = { id: 7, companyId: 2, projectId: 3, projectName: 'Объект', cableBrand: 'ВВГ', cableType: '', lengthInstalled: 2, normatives: 'confirmed' };
const styles = { C: {}, card: {}, inp: {}, btnB: {}, btnG: {}, btnO: {} };
const originalFetch = global.fetch;
const masterScopeProps = () => {
  const user = { id: 1, name: 'Мастер' };
  const companyContext = { mode: 'company', selectedCompanyId: 2, companies: [{ companyId: 2, role: 'прораб' }] };
  return { user, companyContext, qualityJournalLoadState: { cables: { status: 'ready', complete: true,
    scopeKey: qualityJournalScopeKey(companyContext, user), revision: getQualityJournalRevision() } } };
};
beforeEach(() => { require('../utils/qualityJournalEvents').resetTestState(); localStorage.clear(); global.fetch = jest.fn(); });
afterEach(() => { global.fetch = originalFetch; });

function Editor({ kind, saved, record = cable, builder = jest.fn(), preview = jest.fn() }) {
  const [draft, setDraft] = useState(record);
  if (!draft) return <span>Closed</span>;
  return kind === 'cable'
    ? <ProjectCableJournalEditModal {...styles} cable={draft} setEditingCable={setDraft} setCableJournal={saved} cableTypeOf={() => 'Силовой кабель'} showPreview={preview} buildCableJournalContent={builder} />
    : <ProjectMaterialInspectionEditModal {...styles} inspection={draft} setEditingInspection={setDraft} setMaterialInspections={saved} showPreview={preview} buildMaterialInspectionContent={builder} />;
}

test.each(['cable', 'inspection'])('%s prints exact identity but blocks unsaved draft printing', async kind => {
  const builder = jest.fn(() => 'document');
  const preview = jest.fn();
  render(<Editor kind={kind} saved={jest.fn()} builder={builder} preview={preview} />);
  fireEvent.click(screen.getByRole('button', { name: /Печать/ }));
  expect(builder.mock.calls[0][0]).toEqual([cable]);
  expect(builder.mock.calls[0][1]).toEqual({ id: 3, companyId: 2, name: 'Объект' });
  const input = kind === 'cable' ? screen.getByPlaceholderText('напр. барабан №47') : screen.getByPlaceholderText('напр. №147');
  fireEvent.change(input, { target: { value: 'UNSAVED' } });
  fireEvent.click(screen.getByRole('button', { name: /Печать/ }));
  expect(builder).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/Сохраните изменения перед печатью/)).toBeInTheDocument();
  fetch.mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: 'Конфликт' }) });
  fireEvent.click(screen.getByRole('button', { name: /^Сохранить$/ }));
  await screen.findByRole('alert');
  expect(screen.getByRole('button', { name: /Печать/ })).toBeDisabled();
  expect(builder).toHaveBeenCalledTimes(1);
});

test.each(['cable', 'inspection'])('%s print guard errors are inline and do not open preview', kind => {
  const preview = jest.fn();
  render(<Editor kind={kind} saved={jest.fn()} builder={() => { throw new Error('Журнал загружен не полностью'); }} preview={preview} />);
  fireEvent.click(screen.getByRole('button', { name: /Печать/ }));
  expect(screen.getByRole('alert')).toHaveTextContent('Журнал загружен не полностью');
  expect(preview).not.toHaveBeenCalled();
});

test.each(['cable', 'inspection'])('%s HTTP failure keeps draft and confirmed list intact, then saves', async kind => {
  fetch.mockResolvedValueOnce({ ok: false, status: 409, json: async () => ({ detail: 'Конфликт журнала' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ ok: true }) });
  const saved = jest.fn();
  render(<Editor kind={kind} saved={saved} />);
  const input = kind === 'cable' ? screen.getByPlaceholderText('напр. барабан №47') : screen.getByPlaceholderText('напр. №147');
  fireEvent.change(input, { target: { value: 'draft-123' } });
  fireEvent.click(screen.getByRole('button', { name: /^Сохранить$/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Конфликт журнала');
  expect(input).toHaveValue('draft-123');
  expect(saved).not.toHaveBeenCalled();
  expect(screen.queryByText('Closed')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /^Сохранить$/ }));
  await screen.findByText('Closed');
  expect(saved).toHaveBeenCalledTimes(1);
  expect(screen.getByText('Closed')).toBeInTheDocument();
  expect(JSON.parse(fetch.mock.calls[0][1].body)).not.toHaveProperty('cableType');
});

test('master uses separate drafts and prints confirmed record on failure', async () => {
  fetch.mockResolvedValue({ ok: false, status: 403, json: async () => ({ detail: 'Нет доступа' }) });
  const saved = jest.fn();
  const builder = jest.fn(() => 'document');
  render(<MasterCablePage {...styles} {...masterScopeProps()} API="" projects={[{ id: 3, companyId: 2, name: 'Объект' }]} cableJournal={[cable]} setCableJournal={saved} cableTypeOf={() => 'Силовой кабель'} showPreview={jest.fn()} buildCableJournalContent={builder} />);
  const input = screen.getByPlaceholderText('Проложено, м');
  fireEvent.change(input, { target: { value: '7' } });
  expect(saved).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: /Сохранить монтаж/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Нет доступа');
  expect(input).toHaveValue(7);
  expect(saved).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Печать' }));
  expect(builder.mock.calls[0][0][0].lengthInstalled).toBe(2);
  expect(builder.mock.calls[0][1]).toEqual({ id: 3, companyId: 2, name: 'Объект' });
  expect(JSON.parse(fetch.mock.calls[0][1].body)).not.toHaveProperty('cableType');
});

test.each(['cable', 'inspection'])('%s late AI success cannot update a replacement modal', async kind => {
  let finish;
  fetch.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const saved = jest.fn();
  const edit = jest.fn();
  const modal = record => kind === 'cable'
    ? <ProjectCableJournalEditModal {...styles} cable={record} setEditingCable={edit} setCableJournal={saved} cableTypeOf={() => 'Кабель'} />
    : <ProjectMaterialInspectionEditModal {...styles} inspection={record} setEditingInspection={edit} setMaterialInspections={saved} />;
  const view = render(modal(cable));
  fireEvent.click(screen.getByRole('button', { name: /AI-подсказка/ }));
  expect(screen.getByRole('button', { name: /^Сохранить$/ })).toBeDisabled();
  expect(screen.getByRole('status')).toHaveTextContent('Обработка');
  view.rerender(modal({ ...cable, id: 8 }));
  await act(async () => finish({ ok: true, json: async () => ({ ok: true, normatives: 'late', aiFilled: true }) }));
  expect(saved).not.toHaveBeenCalled();
  expect(edit).not.toHaveBeenCalled();
});

test.each(['cable', 'inspection'])('%s AI failure preserves draft and shows an inline error', async kind => {
  fetch.mockResolvedValue({ ok: false, status: 503, json: async () => ({ detail: 'ИИ недоступен' }) });
  const saved = jest.fn();
  render(<Editor kind={kind} saved={saved} />);
  const input = kind === 'cable' ? screen.getByPlaceholderText('напр. барабан №47') : screen.getByPlaceholderText('напр. №147');
  fireEvent.change(input, { target: { value: 'keep me' } });
  fireEvent.click(screen.getByRole('button', { name: /AI-подсказка/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent('ИИ недоступен');
  expect(input).toHaveValue('keep me');
  expect(saved).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: /^Сохранить$/ })).not.toBeDisabled();
});

test('master successful save updates confirmed print and does not resend inferred cable type', async () => {
  fetch.mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  const builder = jest.fn(() => 'document');
  function Master() {
    const [rows, setRows] = useState([cable]);
    return <MasterCablePage {...styles} {...masterScopeProps()} API="" projects={[{ id: 3, companyId: 2, name: 'Объект' }]} cableJournal={rows} setCableJournal={setRows} cableTypeOf={() => 'Силовой кабель'} showPreview={jest.fn()} buildCableJournalContent={builder} />;
  }
  render(<Master />);
  fireEvent.change(screen.getByPlaceholderText('Проложено, м'), { target: { value: '7' } });
  fireEvent.click(screen.getByRole('button', { name: /Сохранить монтаж/ }));
  await screen.findByText('Запись сохранена');
  fireEvent.click(screen.getByRole('button', { name: 'Печать' }));
  expect(builder.mock.calls[0][0][0].lengthInstalled).toBe(7);
  expect(screen.getByRole('status')).toHaveTextContent('Запись сохранена');
});

test.each(['cable', 'inspection'])('%s close while saving ignores a late result', async kind => {
  let finish;
  fetch.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const saved = jest.fn();
  render(<Editor kind={kind} saved={saved} />);
  fireEvent.click(screen.getByRole('button', { name: /^Сохранить$/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Отмена' }));
  await act(async () => finish({ ok: true, json: async () => ({ ok: true }) }));
  expect(saved).not.toHaveBeenCalled();
  expect(screen.getByText('Closed')).toBeInTheDocument();
});

test.each(['error', 'loading', 'missing', 'stale'])('master %s load is not presented as an empty journal', status => {
  const props = masterScopeProps();
  if (status === 'missing') props.qualityJournalLoadState = {};
  else if (status === 'stale') props.qualityJournalLoadState.cables.revision -= 1;
  else props.qualityJournalLoadState.cables = { ...props.qualityJournalLoadState.cables, status, complete: false, error: status === 'error' ? 'Доступ запрещён' : '' };
  render(<MasterCablePage {...styles} {...props} projects={[]} cableJournal={[]} cableTypeOf={() => 'Кабель'} />);
  expect(screen.getByRole('alert')).toBeInTheDocument();
  expect(screen.queryByText('Кабельных позиций пока нет.')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Печать/ })).not.toBeInTheDocument();
});

test('master uses exact project identity and does not show same-name foreign rows', () => {
  render(<MasterCablePage {...styles} {...masterScopeProps()} projects={[{ id: 4, companyId: 2, name: 'Объект' }]}
    cableJournal={[cable]} cableTypeOf={() => 'Кабель'} />);
  expect(screen.queryByText('ВВГ')).not.toBeInTheDocument();
});

test.each(['complete', 'company-change'])('master pending row survives blocked loader state: %s', async next => {
  let finish;
  fetch.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const saved = jest.fn();
  function Master({ changedCompany = false, reloaded = false }) {
    const [rows, setRows] = useState([cable, { ...cable, id: 8 }]);
    const [load, setLoad] = useState(masterScopeProps().qualityJournalLoadState);
    useEffect(() => {
      const listener = () => setLoad({ cables: { ...masterScopeProps().qualityJournalLoadState.cables,
        status: getQualityJournalMutationState().pendingCount ? 'blocked' : 'loading', complete: false } });
      window.addEventListener(QUALITY_JOURNAL_MUTATED, listener);
      return () => window.removeEventListener(QUALITY_JOURNAL_MUTATED, listener);
    }, []);
    const props = masterScopeProps();
    if (changedCompany) props.companyContext = { ...props.companyContext, selectedCompanyId: 3 };
    return <MasterCablePage {...styles} {...props} qualityJournalLoadState={reloaded ? props.qualityJournalLoadState : load} API=""
      projects={[{ id: 3, companyId: 2, name: 'Объект' }]} cableJournal={rows}
      setCableJournal={update => { saved(); setRows(update); }} cableTypeOf={() => 'Кабель'} />;
  }
  const view = render(<Master />);
  fireEvent.change(screen.getAllByPlaceholderText('Проложено, м')[0], { target: { value: '7' } });
  fireEvent.click(screen.getAllByRole('button', { name: /Сохранить монтаж/ })[0]);
  expect(screen.getByRole('alert')).toBeInTheDocument();
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(false);
  expect(screen.getAllByRole('button', { name: /Сохранить монтаж|Печать/ }).every(button => button.disabled)).toBe(true);
  expect(screen.getAllByPlaceholderText('Проложено, м')[0]).toHaveValue(7);
  if (next === 'company-change') {
    view.rerender(<Master changedCompany />);
  }
  expect(screen.queryAllByPlaceholderText('Проложено, м')).toHaveLength(next === 'complete' ? 2 : 0);
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(next !== 'complete');
  await act(async () => { finish({ ok: true, status: 200, json: async () => ({ ok: true }) }); });
  expect(saved).toHaveBeenCalledTimes(next === 'complete' ? 1 : 0);
  expect(getQualityJournalMutationState()).toMatchObject({ pendingCount: 0, uncertain: next !== 'complete' });
  expect(screen.queryAllByRole('button', { name: /Сохранить монтаж|Печать/ }).every(button => button.disabled)).toBe(true);
  view.rerender(<Master reloaded={next === 'complete'} changedCompany={next !== 'complete'} />);
  expect(screen.queryAllByRole('alert')).toHaveLength(next === 'complete' ? 0 : 1);
  expect(screen.queryAllByPlaceholderText('Проложено, м').map(input => input.value)).toEqual(next === 'complete' ? ['7', '2'] : []);
  expect(screen.queryAllByRole('button', { name: /Сохранить монтаж|Печать/ }).every(button => !button.disabled)).toBe(true);
});
