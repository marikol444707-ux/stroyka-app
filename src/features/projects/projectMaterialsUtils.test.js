import { projectMaterialEstimateDetailsToLoad } from './projectMaterialsUtils';

describe('projectMaterialEstimateDetailsToLoad', () => {
  it('returns only unloaded active customer and material estimates without duplicates', () => {
    const rowsByKind = {
      'Заказчик': [
        { id: 1, projectName: 'Лицей', smetaType: 'Заказчик', sectionsLoaded: false },
        { id: 2, projectName: 'Лицей', smetaType: 'Заказчик', sectionsLoaded: true, sections: [] },
      ],
      'Материалы': [
        { id: 1, projectName: 'Лицей', smetaType: 'Материалы', sectionsLoaded: false },
        { id: 3, projectName: 'Лицей', smetaType: 'Материалы', sectionsLoaded: false },
      ],
    };
    const activeEstimatesForProject = (_project, kind) => rowsByKind[kind] || [];

    expect(projectMaterialEstimateDetailsToLoad({
      project: { id: 10, name: 'Лицей' },
      activeEstimatesForProject,
    }).map(row => row.id)).toEqual([1, 3]);
  });

  it('returns no rows when the project has no active estimate details to load', () => {
    expect(projectMaterialEstimateDetailsToLoad({
      project: { id: 10, name: 'Лицей' },
      activeEstimatesForProject: () => [],
    })).toEqual([]);
  });
});
