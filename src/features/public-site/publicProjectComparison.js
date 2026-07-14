const wallTypeLabels = {
  gasblock: 'Газоблок',
  brick: 'Кирпич',
  monolith: 'Монолит',
  frame: 'Каркас',
};

export const parsePublicProjectComparisonCodes = (value, projects = []) => {
  const allowedCodes = new Set(projects.map((project) => project.code).filter(Boolean));
  const parsed = String(value || '')
    .split(',')
    .map((code) => code.trim())
    .filter((code) => allowedCodes.has(code));
  return [...new Set(parsed)].slice(0, 3);
};

export const buildPublicProjectComparisonUrl = ({
  origin,
  pathname = '/',
  selectedCode,
  comparedCodes = [],
}) => {
  const url = new URL(pathname || '/', origin);
  if (selectedCode) url.searchParams.set('project', selectedCode);
  if (comparedCodes.length) url.searchParams.set('compare', comparedCodes.slice(0, 3).join(','));
  url.hash = 'projects';
  return url.toString();
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
