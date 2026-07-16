import { buildProjectsPageContext } from './buildProjectsPageContext';

describe('buildProjectsPageContext', () => {
  it('preserves project data, authenticated context, actions, and responsive layout', () => {
    const user = { id: 7, role: 'директор' };
    const projects = [{ id: 1, name: 'Кисловодск Лицей 4' }];
    const estimatesList = [{ id: 25, projectName: projects[0].name }];
    const openProject = jest.fn();
    const saveProject = jest.fn();

    const result = buildProjectsPageContext({
      API: '/api',
      actions: { openProject },
      appMainState: { estimatesList, projects, user },
      layout: { isMobile: true },
      projectCrudActions: { saveProject },
      selectors: { selectedProject: projects[0] },
      ui: { activeProjectTab: 'overview' },
    });

    expect(result.API).toBe('/api');
    expect(result.user).toBe(user);
    expect(result.projects).toBe(projects);
    expect(result.estimatesList).toBe(estimatesList);
    expect(result.selectedProject).toBe(projects[0]);
    expect(result.openProject).toBe(openProject);
    expect(result.saveProject).toBe(saveProject);
    expect(result.activeProjectTab).toBe('overview');
    expect(result.isMobile).toBe(true);
  });

  it('keeps explicitly supplied actions ahead of lower-level action groups', () => {
    const explicitAction = jest.fn();
    const operationAction = jest.fn();

    const result = buildProjectsPageContext({
      actions: { openProject: explicitAction },
      projectOperationActions: { openProject: operationAction },
    });

    expect(result.openProject).toBe(explicitAction);
  });
});
