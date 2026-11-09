import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ProjectSupervisorActsTab from './ProjectSupervisorActsTab';
import ProjectInspectionOrdersTab from './ProjectInspectionOrdersTab';
import SupervisorCabinetPage from '../../components/SupervisorCabinetPage';
import { buildSupervisorMonthlyReportDocContent } from '../../utils/print/regulatoryDocumentBuilders';

const project = { id: 11, companyId: 2, name: 'Школа' };
const own = { id: 1, companyId: 2, projectId: 11, projectName: 'Старое имя',
  description: 'OWN', actNumber: 'A1', actType: 'Осмотр', date: '2026-11-01' };
const foreign = { ...own, id: 2, companyId: 3, projectName: 'Школа', description: 'FOREIGN' };
const legacy = { id: 3, projectName: 'Школа', description: 'UNASSIGNED', date: '2026-11-01' };
const rows = [own, foreign, legacy];
const props = { project, C: {}, card: {}, Plus: () => null, Check: () => null, Trash2: () => null,
  badge: () => ({}), createInspectionOrderForm: () => ({}), refreshData: jest.fn(),
  setNewInspOrder: jest.fn(), setShowForm: jest.fn() };

test.each([ProjectSupervisorActsTab, ProjectInspectionOrdersTab])('%p uses exact company and project', Tab => {
  render(<Tab {...props} supervisorActs={rows} inspectionOrders={rows} />);
  expect(screen.getByText('OWN')).toBeInTheDocument();
  expect(screen.queryByText('FOREIGN')).not.toBeInTheDocument();
  expect(screen.queryByText('UNASSIGNED')).not.toBeInTheDocument();
});

test('monthly report selects owned supervisor acts and rejects ambiguous project names', () => {
  const context = { projects: [project, { ...project, id: 12, companyId: 3 }], supervisorActs: rows };
  const html = buildSupervisorMonthlyReportDocContent(project, '', '', context);
  expect(html).toContain('OWN');
  expect(html).not.toContain('FOREIGN');
  expect(html).not.toContain('UNASSIGNED');
  expect(() => buildSupervisorMonthlyReportDocContent('Школа', '', '', context)).toThrow();
});

test.each([409, 403, 500])('inspection save keeps draft on HTTP %s', async status => {
  const originalFetch = global.fetch;
  const alert = jest.spyOn(window, 'alert').mockImplementation(() => {});
  const setDraft = jest.fn(), setForm = jest.fn(), refresh = jest.fn();
  global.fetch = jest.fn(async () => ({ ok: false, status, json: async () => ({ detail: 'Запись отклонена' }) }));
  try {
    render(<ProjectInspectionOrdersTab {...props} API="/api" inspectionOrders={[]} showForm="gsn"
      newInspOrder={{ description: 'Локальный черновик' }} setNewInspOrder={setDraft}
      setShowForm={setForm} refreshData={refresh} />);
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
    await waitFor(() => expect(alert).toHaveBeenCalledWith(expect.stringContaining('Запись отклонена')));
    expect(setDraft).not.toHaveBeenCalled();
    expect(setForm).not.toHaveBeenCalled();
    expect(refresh).not.toHaveBeenCalled();
    expect(screen.getByDisplayValue('Локальный черновик')).toBeInTheDocument();
  } finally { global.fetch = originalFetch; alert.mockRestore(); }
});

test('supervisor rejection preserves the act and does not announce success', async () => {
  const originalFetch = global.fetch;
  const alert = jest.spyOn(window, 'alert').mockImplementation(() => {});
  const setDraft = jest.fn(), setForm = jest.fn(), refresh = jest.fn(), setPhoto = jest.fn();
  global.fetch = jest.fn(async () => ({ ok: false, status: 409, json: async () => ({ detail: 'Объект изменился' }) }));
  try {
    render(<SupervisorCabinetPage C={{}} projects={[project]} workJournal={[]} user={{ id: 21,
      name: 'Инспектор', role: 'технадзор', companyId: 2, projectId: 11 }}
      companyContext={{ mode: 'company', selectedCompanyId: 2, companies: [{ companyId: 2, role: 'технадзор' }] }}
      listSearch="" matchSearch={() => true} computeNotifications={() => []}
      projectRealProgress={() => 0} projectPlanDone={() => ({ done: 0 })}
      checklists={[]} prescriptionsList={[]} supervisorActs={[]} materialInspections={[]} hiddenActs={[]}
      showForm="svact" newSupervisorAct={{ description: 'Мой акт', actType: 'Осмотр', findings: '', recommendations: '', date: '' }}
      setNewSupervisorAct={setDraft} setShowForm={setForm} refreshData={refresh}
      supervisorActPhoto="" setSupervisorActPhoto={setPhoto} />);
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
    await waitFor(() => expect(alert).toHaveBeenCalledWith(expect.stringContaining('Объект изменился')));
    expect(setDraft).not.toHaveBeenCalled();
    expect(setForm).not.toHaveBeenCalled();
    expect(setPhoto).not.toHaveBeenCalled();
    expect(refresh).not.toHaveBeenCalled();
    expect(alert).not.toHaveBeenCalledWith('Акт сохранён');
    expect(screen.getByDisplayValue('Мой акт')).toBeInTheDocument();
    const payload = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(payload.projectId).toBe(11);
  } finally { global.fetch = originalFetch; alert.mockRestore(); }
});
