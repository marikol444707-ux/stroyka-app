import { createDirectorDashboardActions } from '../dashboard/directorDashboardActions';
import { createProjectDashboardRuntime } from '../dashboard/projectDashboardRuntime';

export function createAppDashboardRuntime({
  directorDashboardOptions,
  lowStockFor,
  materials,
  projectDashboardOptions,
  warehouseMain,
}) {
  const documentActionRefs = {};
  const projectDashboardRuntime = createProjectDashboardRuntime({
    ...projectDashboardOptions,
    buildMaterialRequirementContent: (...args) => (
      documentActionRefs.buildMaterialRequirementContent?.(...args) || ''
    ),
  });
  const lowStock = lowStockFor(materials);
  const lowMainStock = lowStockFor(warehouseMain);
  const directorDashboardActions = createDirectorDashboardActions({
    ...directorDashboardOptions,
    lowMainStock,
    lowStock,
    projectBudgetSpent: projectDashboardRuntime.projectBudgetSpent,
  });

  return {
    ...projectDashboardRuntime,
    ...directorDashboardActions,
    documentActionRefs,
    lowMainStock,
    lowStock,
  };
}
