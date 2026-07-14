const wallTypeLabels = {
  gasblock: 'Газоблок',
  brick: 'Кирпич',
  monolith: 'Монолит',
  frame: 'Каркас',
};

export const buildPublicProjectComparisonItem = ({ project = {}, estimate = {} }) => {
  const calc = project.calcPatch || {};
  const isHouse = (calc.type || 'house') === 'house';
  const facts = [
    ['Площадь', project.area || 'уточняется'],
    ['Этажность / формат', project.floors || 'уточняется'],
  ];
  if (calc.rooms) facts.push(['Комнат / зон', String(calc.rooms)]);
  if (isHouse && calc.bedrooms) facts.push(['Спален', String(calc.bedrooms)]);
  if (isHouse && calc.wallType) facts.push(['Материал стен', wallTypeLabels[calc.wallType] || calc.wallType]);
  facts.push(['Ориентир', estimate.rangeLabel || estimate.fromLabel || 'после уточнения']);

  return {
    code: project.code || '',
    title: project.title || 'Проект',
    facts,
    project,
  };
};
