import { createDirectorDashboardActions } from '../dashboard/directorDashboardActions';
import { createProjectDashboardRuntime } from '../dashboard/projectDashboardRuntime';
import { createAppDashboardRuntime } from './createAppDashboardRuntime';

jest.mock('../dashboard/directorDashboardActions', () => ({
  createDirectorDashboardActions: jest.fn(),
}));

jest.mock('../dashboard/projectDashboardRuntime', () => ({
  createProjectDashboardRuntime: jest.fn(),
}));

describe('createAppDashboardRuntime', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('composes dashboard runtimes, stock alerts, and deferred document action', () => {
    const materials = [{ id: 'project-stock' }];
    const warehouseMain = [{ id: 'main-stock' }];
    const lowStock = [{ id: 'project-low' }];
    const lowMainStock = [{ id: 'main-low' }];
    const lowStockFor = jest.fn((rows) => (
      rows === materials ? lowStock : lowMainStock
    ));

    createProjectDashboardRuntime.mockReturnValue({
      projectBudgetSpent: jest.fn(),
      projectDashboardValue: 'project',
    });
    createDirectorDashboardActions.mockReturnValue({
      directorDashboardValue: 'director',
    });

    const runtime = createAppDashboardRuntime({
      directorDashboardOptions: { companyName: 'СтройКа' },
      lowStockFor,
      materials,
      projectDashboardOptions: { user: { role: 'директор' } },
      warehouseMain,
    });

    const projectOptions = createProjectDashboardRuntime.mock.calls[0][0];
    expect(projectOptions.user).toEqual({ role: 'директор' });
    expect(projectOptions.buildMaterialRequirementContent('before')).toBe('');

    runtime.documentActionRefs.buildMaterialRequirementContent = jest.fn(() => 'document');
    expect(projectOptions.buildMaterialRequirementContent('after')).toBe('document');
    expect(runtime.documentActionRefs.buildMaterialRequirementContent).toHaveBeenCalledWith('after');

    expect(lowStockFor).toHaveBeenNthCalledWith(1, materials);
    expect(lowStockFor).toHaveBeenNthCalledWith(2, warehouseMain);
    expect(createDirectorDashboardActions).toHaveBeenCalledWith(expect.objectContaining({
      companyName: 'СтройКа',
      lowMainStock,
      lowStock,
      projectBudgetSpent: runtime.projectBudgetSpent,
    }));
    expect(runtime).toEqual(expect.objectContaining({
      directorDashboardValue: 'director',
      lowMainStock,
      lowStock,
      projectDashboardValue: 'project',
    }));
  });
});
