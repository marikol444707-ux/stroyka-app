import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import SupervisorCabinetPage from './SupervisorCabinetPage';
import AccountingDocumentsPanel from './AccountingDocumentsPanel';
import ProjectOverviewTab from '../features/projects/ProjectOverviewTab';
import { qualityJournalScopeKey } from '../utils/qualityJournalScope';
import { getQualityJournalRevision } from '../utils/qualityJournalEvents';
import { buildAppRenderContext } from '../features/app-shell/buildAppRenderContext';

jest.mock('./ProjectHiddenWorksActSignatureModal', () => () => null);
jest.mock('./ImagePreviewModal', () => () => null);
jest.mock('./PreviewModal', () => () => null);

const project = { id: 11, companyId: 2, name: 'Школа' };
const user = { id: 7, companyId: 2, projectId: 11, projectName: 'Школа', name: 'Supervisor' };
const companyContext = { mode: 'company', selectedCompanyId: 2, companies: [{ companyId: 2, role: 'технадзор' }] };
const ready = { scopeKey: qualityJournalScopeKey(companyContext, user), status: 'ready', complete: true, revision: getQualityJournalRevision() };
const owned = { id: 1, companyId: 2, projectId: 11, projectName: 'Старое имя', materialName: 'OWN', quantity: 1 };
const props = { user, companyContext, qualityJournalLoadState: { inspections: ready }, projects: [project],
  C: {}, card: {}, projectRealProgress: () => 0, projectPlanDone: () => ({ done: 0 }), computeNotifications: () => [],
  workJournal: [], checklists: [], prescriptionsList: [], hiddenActs: [], supervisorActs: [], materialInspections: [],
  newSupervisorAct: {}, fmtMeasure: String };
const inspectionCard = () => screen.getByText('📦 Входной контроль материалов').parentElement;

test.each(['мастер', 'технадзор'])('early %s route receives live company context and journal completeness', role => {
  const qualityJournalLoadState = { inspections: ready, cables: ready };
  const { earlyRoleRoute } = buildAppRenderContext({
    actionGroups: {
      documentActions: {}, personnelActions: {}, pricelistActions: {}, projectCrudActions: {},
      projectOperationActions: {}, supplyActions: {}, supplyPlanningUi: {}, userAccessActions: {},
      warehouseActions: {}, workJournalActions: {},
    },
    appCoreRuntime: { myNotifications: () => [] },
    appMainState: { qualityJournalLoadState }, companyContext, user: { ...user, role },
  });
  expect(earlyRoleRoute.props.data.companyContext).toBe(companyContext);
  expect(earlyRoleRoute.props.data.qualityJournalLoadState).toBe(qualityJournalLoadState);
});

test('supervisor inspection list uses exact IDs even when another same-name project is first', () => {
  render(<SupervisorCabinetPage {...props} projects={[{ id: 12, companyId: 3, name: 'Школа' }, project]}
    materialInspections={[owned, { ...owned, id: 2, companyId: 3, projectName: 'Школа', materialName: 'FOREIGN' },
      { ...owned, id: 3, projectId: 12, projectName: 'Школа', materialName: 'OTHER_PROJECT' }]} />);
  expect(within(inspectionCard()).getByText('OWN')).toBeInTheDocument();
  expect(within(inspectionCard()).queryByText('FOREIGN')).not.toBeInTheDocument();
  expect(within(inspectionCard()).queryByText('OTHER_PROJECT')).not.toBeInTheDocument();
});

test.each([undefined, { inspections: { ...ready, status: 'error', error: 'HTTP 409' } },
  { inspections: { ...ready, complete: false } }, { inspections: { ...ready, scopeKey: 'old' } },
  { inspections: { ...ready, revision: ready.revision - 1 } }])(
  'failed/missing/stale snapshot is unconfirmed, not empty: %j', qualityJournalLoadState => {
    render(<SupervisorCabinetPage {...props} qualityJournalLoadState={qualityJournalLoadState} />);
    expect(within(inspectionCard()).getByRole('alert')).toHaveTextContent(/не подтвержден/i);
    expect(inspectionCard()).not.toHaveTextContent('Записей нет');
  });

test('switching company immediately hides the previous inspection snapshot', () => {
  const view = render(<SupervisorCabinetPage {...props} materialInspections={[owned]} />);
  expect(within(inspectionCard()).getByText('OWN')).toBeInTheDocument();
  view.rerender(<SupervisorCabinetPage {...props} materialInspections={[owned]}
    companyContext={{ ...companyContext, selectedCompanyId: 3,
      companies: [...companyContext.companies, { companyId: 3, role: 'технадзор' }] }} />);
  expect(screen.getByRole('alert')).toHaveTextContent(/не подтвержден/i);
  expect(screen.queryByText('OWN')).not.toBeInTheDocument();
});

const Icon = () => null;
const makeOverviewContext = buildJPRContent => ({ C: {}, FileText: Icon, ScrollText: Icon, QrCode: Icon, Plus: Icon, X: Icon,
  ProjectObjectLinksPanel: Icon, projectObjectLinks: () => [], buildJPRContent, showPreview: jest.fn(),
  brigadeContracts: [], estimatesList: [], visibleEstimatesForCurrentUser: rows => rows,
  projectPlanDone: () => ({ plan: 0 }), workJournal: [], newTask: '', user: null });
const makeAccountingProps = buildJPRContent => ({ C: {}, projects: [project], accountingDocProject: project.name,
  projectPlanDone: () => ({ plan: 0, done: 0 }), materialControlSummaryForProject: () => ({ outsideRows: [], stockMismatchRows: [], toBuyRows: [] }),
  projectPayments: [], interimActs: [], buildJPRContent, showPreview: jest.fn(), badge: () => ({}) });

test('overview JPR passes the selected project object unchanged', () => {
  const ctx = makeOverviewContext(jest.fn(() => 'HTML'));
  render(<ProjectOverviewTab project={project} ctx={ctx} />);
  fireEvent.click(screen.getByRole('button', { name: 'ЖПР' }));
  expect(ctx.buildJPRContent).toHaveBeenCalledWith(project);
  expect(ctx.showPreview).toHaveBeenCalledWith('HTML', 'ЖПР — Школа');
});

test('overview shows guard failure and does not open a preview; retry clears the message', () => {
  const ctx = makeOverviewContext(jest.fn().mockImplementationOnce(() => { throw new Error('Журнал не загружен'); }).mockReturnValue('HTML'));
  render(<ProjectOverviewTab project={project} ctx={ctx} />);
  fireEvent.click(screen.getByRole('button', { name: 'ЖПР' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Журнал не загружен');
  expect(ctx.showPreview).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'ЖПР' }));
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(ctx.showPreview).toHaveBeenCalledTimes(1);
});

test('accounting JPR passes the resolved project object unchanged', () => {
  const accountingProps = makeAccountingProps(jest.fn(() => 'HTML'));
  render(<AccountingDocumentsPanel {...accountingProps} />);
  fireEvent.click(screen.getByRole('button', { name: 'ЖПР' }));
  expect(accountingProps.buildJPRContent).toHaveBeenCalledWith(project);
  expect(accountingProps.showPreview).toHaveBeenCalledWith('HTML', 'ЖПР');
});

test('accounting shows guard failure without opening preview; retry clears the message', () => {
  const accountingProps = makeAccountingProps(jest.fn().mockImplementationOnce(() => { throw new Error('Область журнала не подтверждена'); }).mockReturnValue('HTML'));
  render(<AccountingDocumentsPanel {...accountingProps} />);
  fireEvent.click(screen.getByRole('button', { name: 'ЖПР' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Область журнала не подтверждена');
  expect(accountingProps.showPreview).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'ЖПР' }));
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(accountingProps.showPreview).toHaveBeenCalledTimes(1);
});

test('legacy rows are unconfirmed rather than inferred by name', () => {
  render(<SupervisorCabinetPage {...props} materialInspections={[{ id: 1, projectName: 'Школа', materialName: 'LEGACY' }]} />);
  expect(within(inspectionCard()).getByRole('alert')).toHaveTextContent(/не подтвержден/i);
  expect(within(inspectionCard()).queryByText('LEGACY')).not.toBeInTheDocument();
});

test('a confirmed empty inspection list stays empty', () => {
  render(<SupervisorCabinetPage {...props} />);
  expect(inspectionCard()).toHaveTextContent('Записей нет');
  expect(within(inspectionCard()).queryByRole('alert')).not.toBeInTheDocument();
});

test.each([{ ...user, projectId: null }, { ...user, projectId: 999 }, { ...user, project_id: 12 }])(
  'unproven or conflicting project assignment never falls back to a name: %j', actor => {
    render(<SupervisorCabinetPage {...props} user={actor} materialInspections={[owned]} />);
    expect(screen.getByRole('alert')).toHaveTextContent(/не подтвержден/i);
    expect(screen.queryByText('📦 Входной контроль материалов')).not.toBeInTheDocument();
  });
