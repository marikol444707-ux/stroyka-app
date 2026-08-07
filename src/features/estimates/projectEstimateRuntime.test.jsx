import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { createProjectEstimateRuntime } from './projectEstimateRuntime';
import {
  immutableStoredProjectOwner,
  positiveStoredId,
  sameStoredProjectOwner,
  uniqueStoredProjectForName,
} from './projectEstimateOwnership';

const createOwnershipRuntime = (estimatesList) => createProjectEstimateRuntime({
  ESTIMATE_PACKAGES: ['Основная'],
  estimatesList,
  projects: [],
  rooms: [],
  roomDoors: [],
  roomWindows: [],
  unexpectedWorksList: [],
  user: {},
  visibleEstimatesForCurrentUser: rows => rows,
  workJournal: [],
});

const activeEstimate = ({ id, companyId, projectId, smetaType = 'Заказчик' }) => ({
  id,
  companyId,
  projectId,
  projectName: 'Школа',
  smetaType,
  workPackage: 'Основная',
  status: 'Активная',
});

describe('active estimate project ownership', () => {
  test('parses only positive decimal integer IDs', () => {
    expect(positiveStoredId(7)).toBe(7);
    expect(positiveStoredId('7')).toBe(7);
    expect(positiveStoredId(' 7 ')).toBe(7);
    [null, undefined, '', '0', '01', 0, -1, 1.5, true, [1], {}, Number.MAX_SAFE_INTEGER + 1]
      .forEach(value => expect(positiveStoredId(value)).toBeNull());
  });

  test('matches only the exact stored company and project tuple', () => {
    const project = { id: 11, companyId: 1, name: 'Школа' };

    expect(sameStoredProjectOwner(project, activeEstimate({ id: 101, companyId: 1, projectId: 11 }))).toBe(true);
    expect(sameStoredProjectOwner(project, activeEstimate({ id: 102, companyId: 2, projectId: 11 }))).toBe(false);
    expect(sameStoredProjectOwner(project, activeEstimate({ id: 103, companyId: 1, projectId: 22 }))).toBe(false);
    expect(sameStoredProjectOwner(project, activeEstimate({ id: 104, companyId: null, projectId: 11 }))).toBe(false);
    expect(sameStoredProjectOwner(project, {
      ...activeEstimate({ id: 105, companyId: 1, projectId: 11 }),
      projectName: 'Другая школа',
    })).toBe(false);
  });

  test('creates an immutable canonical owner from a stored project or owner object', () => {
    const projectOwner = immutableStoredProjectOwner({ id: '11', companyId: '1', name: 'Школа' });
    const existingOwner = immutableStoredProjectOwner({ companyId: 2, projectId: 22, projectName: 'Лицей' });

    expect(projectOwner).toEqual({ companyId: 1, projectId: 11, projectName: 'Школа' });
    expect(existingOwner).toEqual({ companyId: 2, projectId: 22, projectName: 'Лицей' });
    expect(Object.isFrozen(projectOwner)).toBe(true);
    expect(Object.isFrozen(existingOwner)).toBe(true);
  });

  test('rejects incomplete or internally conflicting owner objects', () => {
    expect(immutableStoredProjectOwner({ id: 11, name: 'Школа' })).toBeNull();
    expect(immutableStoredProjectOwner({ id: 11, companyId: 1, name: '' })).toBeNull();
    expect(immutableStoredProjectOwner({ id: 11, projectId: 22, companyId: 1, name: 'Школа' })).toBeNull();
    expect(immutableStoredProjectOwner({ id: 11, companyId: 1, name: 'Школа', projectName: 'Лицей' })).toBeNull();
  });

  test('resolves a legacy name only when one stored owner matches', () => {
    const first = { id: 11, companyId: 1, name: 'Школа' };
    const second = { id: 22, companyId: 2, name: 'Школа' };

    expect(uniqueStoredProjectForName([first], 'Школа')).toBe(first);
    expect(uniqueStoredProjectForName([first, second], 'Школа')).toBeNull();
    expect(uniqueStoredProjectForName([{ id: 11, name: 'Лицей' }], 'Лицей')).toBeNull();
  });

  test('isolates same-name customer and material estimates by company and project IDs', () => {
    const firstProject = { id: 11, companyId: 1, name: 'Школа' };
    const secondProject = { id: 22, companyId: 2, name: 'Школа' };
    const runtime = createOwnershipRuntime([
      activeEstimate({ id: 101, companyId: 1, projectId: 11 }),
      activeEstimate({ id: 102, companyId: 1, projectId: 11, smetaType: 'Материалы' }),
      activeEstimate({ id: 201, companyId: 2, projectId: 22 }),
      activeEstimate({ id: 202, companyId: 2, projectId: 22, smetaType: 'Материалы' }),
    ]);

    expect(runtime.activeEstimatesForProject(firstProject, 'Заказчик').map(row => row.id)).toEqual([101]);
    expect(runtime.activeEstimatesForProject(firstProject, 'Материалы').map(row => row.id)).toEqual([102]);
    expect(runtime.activeEstimatesForProject(secondProject, 'Заказчик').map(row => row.id)).toEqual([201]);
    expect(runtime.activeEstimatesForProject(secondProject, 'Материалы').map(row => row.id)).toEqual([202]);
  });

  test('fails closed for missing, malformed, or mismatched stored owners', () => {
    const project = { id: 11, companyId: 1, name: 'Школа' };
    const runtime = createOwnershipRuntime([
      activeEstimate({ id: 1, companyId: null, projectId: 11 }),
      activeEstimate({ id: 2, companyId: true, projectId: 11 }),
      activeEstimate({ id: 3, companyId: [1], projectId: 11 }),
      activeEstimate({ id: 4, companyId: 1, projectId: 11.5 }),
      activeEstimate({ id: 5, companyId: 1, projectId: 99 }),
      activeEstimate({ id: 6, companyId: 2, projectId: 11 }),
    ]);

    expect(runtime.activeEstimatesForProject(project)).toEqual([]);
  });

  test('accepts canonical positive decimal string IDs', () => {
    const project = { id: '11', companyId: '1', name: 'Школа' };
    const runtime = createOwnershipRuntime([
      activeEstimate({ id: 101, companyId: 1, projectId: 11 }),
    ]);

    expect(runtime.activeEstimatesForProject(project).map(row => row.id)).toEqual([101]);
  });

  test('fails closed when an owner has duplicate active estimates in one package', () => {
    const project = { id: 11, companyId: 1, name: 'Школа' };
    const runtime = createOwnershipRuntime([
      activeEstimate({ id: 101, companyId: 1, projectId: 11 }),
      activeEstimate({ id: 102, companyId: 1, projectId: 11 }),
    ]);

    expect(runtime.activeEstimatesForProject(project)).toEqual([]);
  });
});

const budgetProject = {id:14,companyId:4,name:'Лицей'};
const approvedReconciliation = {
  id:15,
  status:'Утверждена',
  baseEstimateId:100,
  nextEstimateId:101,
  baseEstimateName:'База',
  nextEstimateName:'Редакция',
};

const createBudgetRuntime = ({user, companyContext, loadBudgetAdjustmentPreview = jest.fn()} = {}) => (
  createProjectEstimateRuntime({
    ESTIMATE_PACKAGES:[],
    activeTabActions:{openEstimateChanges:jest.fn()},
    approveEstimateReconciliation:jest.fn(),
    approveProjectBudgetAdjustment:jest.fn(),
    companyContext,
    createEstimateChangeFromComparisonRow:jest.fn(),
    createEstimateReconciliation:jest.fn(),
    estimateChangeForComparisonRow:jest.fn(),
    estimateReconciliationsForProject:jest.fn(() => [approvedReconciliation]),
    estimatesList:[],
    loadBudgetAdjustmentPreview,
    loadProjectBudgetAdjustments:jest.fn(),
    openEstimateReconciliationPreview:jest.fn(),
    openProjectEstimateDiffSummary:jest.fn(),
    onBudgetAdjustmentApplied:jest.fn(),
    projects:[budgetProject],
    rooms:[],
    roomDoors:[],
    roomWindows:[],
    showPreview:jest.fn(),
    unexpectedWorksList:[],
    user,
    visibleEstimatesForCurrentUser:rows=>rows,
    workJournal:[],
    workJournalEstimateStatusMeta:jest.fn(),
  })
);

describe('project estimate runtime budget adjustment access', () => {
  it('uses the selected-company role and does not inherit a global director role', () => {
    const runtime = createBudgetRuntime({
      user:{role:'директор'},
      companyContext:{mode:'company',selectedCompany:{companyId:4,role:'сметчик'}},
    });

    render(runtime.renderEstimateReconciliationsPanel(budgetProject));

    expect(screen.queryByText('Изменение бюджета')).not.toBeInTheDocument();
  });

  it('wires the preview action for a leader of the selected company', () => {
    const loadBudgetAdjustmentPreview = jest.fn(() => new Promise(()=>{}));
    const runtime = createBudgetRuntime({
      user:{role:'client_account_owner'},
      companyContext:{mode:'company',selectedCompany:{companyId:4,role:'директор'}},
      loadBudgetAdjustmentPreview,
    });

    render(runtime.renderEstimateReconciliationsPanel(budgetProject));
    fireEvent.click(screen.getByRole('button', {name:/Рассчитать по сверке № 15/}));

    expect(loadBudgetAdjustmentPreview).toHaveBeenCalledWith(15);
  });
});
