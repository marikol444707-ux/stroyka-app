import { itemMatchesWorkRow } from './workAssignmentUtils';


const estimate = {projectName: 'Лицей', workPackage: 'Отделка'};
const row = {
  section: 'Стены',
  name: 'Штукатурка',
  unit: 'м2',
  estimateItemKey: 'work-1',
};

test('assignment status matches only the exact saved compatibility key', () => {
  expect(itemMatchesWorkRow({
    projectName: 'Лицей',
    workPackage: 'Отделка',
    estimateItemKey: 'work-1',
    name: 'Другое отображаемое имя',
  }, row, estimate)).toBe(true);
});

test('same descriptive fields never substitute for a missing lineage key', () => {
  expect(itemMatchesWorkRow({
    projectName: 'Лицей',
    workPackage: 'Отделка',
    estimateItemKey: '',
    estimateSection: 'Стены',
    name: 'Штукатурка',
    unit: 'м2',
  }, row, estimate)).toBe(false);
});
