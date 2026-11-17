import React from 'react';
import { render, screen } from '@testing-library/react';
import ProjectScheduleTab from './ProjectScheduleTab';
import ProjectScheduleSummaryPanel from '../../components/ProjectScheduleSummaryPanel';
import { createProjectDashboardRuntime } from '../dashboard/projectDashboardRuntime';

test('schedule shows saved progress despite material spending and refreshes for another project', () => {
  const project = { id: 12, companyId: 2, name: 'Корпус', budget: 1000, progress: 20 };
  const projectPlanDone = p => p.id === 12 ? { plan: 0, done: 0 } : { plan: 100, done: 125 };
  const runtime = createProjectDashboardRuntime({ projectPlanDone, projectFactSpent: () => ({ total: 1000 }) });
  const view = p => <ProjectScheduleTab project={p} C={{}} card={{}}
    ProjectScheduleSummaryPanel={ProjectScheduleSummaryPanel} projectStages={[]}
    workJournal={[]} projectPayments={[]} supplierInvoices={[]}
    projectPlanDone={projectPlanDone} projectRealProgress={runtime.projectRealProgress}
    materialControlSummaryForProject={() => ({})} />;
  const { rerender } = render(view(project));
  expect(screen.getByText('20%')).toBeInTheDocument();
  expect(screen.queryByText('100%')).not.toBeInTheDocument();
  rerender(view({ ...project, id: 13, companyId: 3 }));
  expect(screen.getByText('100%')).toBeInTheDocument();
  expect(screen.queryByText('125%')).not.toBeInTheDocument();
  rerender(view(project));
  expect(screen.getByText('20%')).toBeInTheDocument();
});
