import { projectRealProgressValue } from './projectEconomyUtils';
import { createProjectDashboardRuntime } from '../features/dashboard/projectDashboardRuntime';

const project = { id: 12, companyId: 2, name: 'Корпус', budget: 1000, progress: 20 };

test.each([0, 400, 1000, 2000])('spending %s does not replace stored progress without an estimate', total => {
  const runtime = createProjectDashboardRuntime({
    projectPlanDone: () => ({ plan: 0, done: 0 }),
    projectFactSpent: () => ({ total }),
  });
  expect(runtime.projectRealProgress(project)).toBe(20);
});

test('materials alone do not complete a project with no recorded progress', () => {
  expect(projectRealProgressValue({ project: { ...project, progress: 0 },
    projectFactSpent: () => ({ total: 1000 }) })).toBe(0);
});

test.each([[100, 125, 100], [100, -5, 0], [100, 33.3, 33],
  [100, 0.1, 1], [100, 0, 0], ['100', '25', 25],
  [100, NaN, 0], [100, Infinity, 0]])('estimate plan %s / done %s produces bounded progress %s', (plan, done, expected) => {
  expect(projectRealProgressValue({ project, projectPlanDone: () => ({ plan, done }) })).toBe(expected);
});

test.each([[120, 100], [-10, 0], ['42', 42], [null, 0], [undefined, 0], ['bad', 0], [Infinity, 0]])(
  'stored progress %s is normalized to %s', (progress, expected) => {
    expect(projectRealProgressValue({ project: { ...project, budget: 0, progress } })).toBe(expected);
  },
);

test('no project has zero progress', () => {
  expect(projectRealProgressValue()).toBe(0);
});
