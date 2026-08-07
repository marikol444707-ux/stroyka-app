import { createProjectEstimateRuntime } from './projectEstimateRuntime';
import {
  positiveStoredId,
  sameStoredProjectOwner,
} from './projectEstimateOwnership';

const createRuntime = (estimatesList) => createProjectEstimateRuntime({
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

  test('isolates same-name customer and material estimates by company and project IDs', () => {
    const firstProject = { id: 11, companyId: 1, name: 'Школа' };
    const secondProject = { id: 22, companyId: 2, name: 'Школа' };
    const runtime = createRuntime([
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
    const runtime = createRuntime([
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
    const runtime = createRuntime([
      activeEstimate({ id: 101, companyId: 1, projectId: 11 }),
    ]);

    expect(runtime.activeEstimatesForProject(project).map(row => row.id)).toEqual([101]);
  });

  test('fails closed when an owner has duplicate active estimates in one package', () => {
    const project = { id: 11, companyId: 1, name: 'Школа' };
    const runtime = createRuntime([
      activeEstimate({ id: 101, companyId: 1, projectId: 11 }),
      activeEstimate({ id: 102, companyId: 1, projectId: 11 }),
    ]);

    expect(runtime.activeEstimatesForProject(project)).toEqual([]);
  });
});
