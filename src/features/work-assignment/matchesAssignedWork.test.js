import {matchesAssignedWork} from './matchesAssignedWork';

const source = {projectName:'Лицей',itemKey:'work-2',itemName:'монтаж кабеля',sectionName:'электрика',itemUnit:'м'};
const assigned = {projectName:'Лицей',estimateItemKey:'work-1',name:'Монтаж кабеля',estimateSection:'Электрика',unit:'м'};

test('does not attach another exact estimate row just because its name matches', () => {
  expect(matchesAssignedWork(assigned, source)).toBe(false);
});
test('matches the exact assigned key even after the name changes', () => {
  expect(matchesAssignedWork({...assigned,estimateItemKey:'work-2',name:'Кабель'},source)).toBe(true);
});
test('preserves name matching for legacy assignment without an exact key', () => {
  expect(matchesAssignedWork({...assigned,estimateItemKey:''},source)).toBe(true);
  expect(matchesAssignedWork({...assigned,estimateItemKey:'',unit:'шт'},source)).toBe(false);
});
test('never matches another project even with the same exact key', () => {
  expect(matchesAssignedWork({...assigned,estimateItemKey:'work-2',projectName:'Школа'},source)).toBe(false);
});
