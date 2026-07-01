import {
  estimateItemTotal,
  estimateTotal,
  isArchivedEstimate,
  isGlobalEstimateTemplate,
  estimateSectionsOf,
} from './estimateUtils';
import { toNum } from './measureUtils';

const normalizeIssueNameKey = (name) => (
  String(name || '')
    .toLowerCase()
    .replace(/[.,;:()«»"']/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
);

const severityRank = (severity) => (severity === 'Критично' ? 0 : 1);

export const buildEstimateControlIssues = ({
  sourceEstimates = [],
  projects = [],
  activeProjects = [],
  activeEstimatesForProject = () => [],
} = {}) => {
  const issues = [];

  (activeProjects || []).forEach(project => {
    if (activeEstimatesForProject(project, 'Заказчик').length === 0) {
      issues.push({
        severity: 'Критично',
        project: project.name,
        estimate: '-',
        where: 'Смета заказчика',
        problem: 'Нет активной сметы заказчика',
        action: 'Назначить или создать активную смету',
      });
    }
  });

  (sourceEstimates || []).filter(estimate => !isGlobalEstimateTemplate(estimate) && !isArchivedEstimate(estimate)).forEach(estimate => {
    const sections = estimateSectionsOf(estimate);
    const projectName = estimate.projectName || projects.find(project => Number(project.id) === Number(estimate.projectId))?.name || '';
    if (!sections.length) {
      issues.push({
        severity: 'Критично',
        project: projectName,
        estimate: estimate.name,
        where: 'Состав сметы',
        problem: 'В смете нет разделов и позиций',
        action: 'Заполнить позиции до запуска работ',
      });
    }

    const seen = {};
    let total = 0;
    sections.forEach(section => (section.items || []).forEach((item, index) => {
      const name = String(item.name || '').trim();
      const qty = toNum(item.quantity);
      const price = toNum(item.priceWork) + toNum(item.priceMaterial);
      total += estimateItemTotal(item);
      const where = `${section.name || 'Раздел'} / ${name || `позиция ${index + 1}`}`;
      if (!name) issues.push({ severity: 'Критично', project: projectName, estimate: estimate.name, where, problem: 'Пустое наименование позиции', action: 'Заполнить название' });
      if (!item.unit) issues.push({ severity: 'Внимание', project: projectName, estimate: estimate.name, where, problem: 'Не указана единица измерения', action: 'Проверить единицу' });
      if (qty <= 0) issues.push({ severity: 'Критично', project: projectName, estimate: estimate.name, where, problem: 'Количество равно нулю или пустое', action: 'Заполнить объём' });
      if (price <= 0) issues.push({ severity: 'Внимание', project: projectName, estimate: estimate.name, where, problem: 'Цена работ и материалов нулевая', action: 'Проверить расценку' });
      const key = normalizeIssueNameKey(name);
      if (key && seen[key]) issues.push({ severity: 'Внимание', project: projectName, estimate: estimate.name, where, problem: 'Возможный дубль позиции', action: `Сравнить с разделом: ${seen[key]}` });
      else if (key) seen[key] = section.name || 'без раздела';
    }));

    const project = projects.find(item => item.name === projectName || Number(item.id) === Number(estimate.projectId));
    if (project && Number(project.budget || 0) > 0 && total > Number(project.budget) * 1.1) {
      issues.push({
        severity: 'Критично',
        project: projectName,
        estimate: estimate.name,
        where: 'Бюджет',
        problem: `Смета выше бюджета объекта на ${Math.round((total / Number(project.budget) - 1) * 100)}%`,
        action: 'Проверить бюджет или состав сметы',
      });
    }
  });

  return issues.sort((a, b) => severityRank(a.severity) - severityRank(b.severity));
};

export const buildEstimateControlReportData = ({ sourceEstimates = [], issues = [] } = {}) => {
  const estimates = (sourceEstimates || []).filter(estimate => !isGlobalEstimateTemplate(estimate));
  const activeEstimates = estimates.filter(estimate => estimate.status === 'Активная');
  const topItems = activeEstimates
    .flatMap(estimate => estimateSectionsOf(estimate).flatMap(section => (section.items || []).map(item => ({
      project: estimate.projectName || '',
      estimate: estimate.name || '',
      section: section.name || '',
      name: item.name || '',
      qty: item.quantity,
      unit: item.unit,
      sum: estimateItemTotal(item),
    }))))
    .filter(item => item.sum > 0)
    .sort((a, b) => b.sum - a.sum)
    .slice(0, 12);
  return {
    estimates,
    activeEstimates,
    issues,
    topItems,
    activeTotal: activeEstimates.reduce((sum, estimate) => sum + estimateTotal(estimate), 0),
  };
};
