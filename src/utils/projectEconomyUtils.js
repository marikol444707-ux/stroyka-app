export const projectMaterialCost = (projectName, materialControlSummaryForProject) => (
  Number(materialControlSummaryForProject?.(projectName)?.suppliedSum || 0)
);

export const projectLaborCost = ({ projectName, allBrigadeItems = [], staff = [], piecework = [], calcSalary = () => 0 }) => {
  const brigadeCost = (allBrigadeItems || [])
    .filter(item => item.projectName === projectName && Number(item.doneQuantity || 0) > 0)
    .reduce((sum, item) => sum + Number(item.doneQuantity || 0) * Number(item.priceBrigade || 0), 0);
  const salaryCost = (staff || [])
    .filter(person => person.project === projectName)
    .reduce((sum, person) => sum + Number(calcSalary(person) || 0), 0);
  const pieceworkCost = (piecework || [])
    .filter(item => item.project === projectName)
    .reduce((sum, item) => sum + Number(item.total || 0), 0);
  return brigadeCost + salaryCost + pieceworkCost;
};

export const projectExpenseCategories = ({
  projectName,
  expenseCategories = [],
  materialControlSummaryForProject,
  allBrigadeItems = [],
  staff = [],
  piecework = [],
  calcSalary = () => 0,
  manualExpenses = [],
  unexpectedWorksList = [],
  accountablePayments = [],
  isApprovedEstimateChangeStatus = () => false,
}) => {
  const result = {};
  (expenseCategories || []).forEach(category => {
    result[category.id] = 0;
  });
  result.materials = projectMaterialCost(projectName, materialControlSummaryForProject);
  result.works = projectLaborCost({ projectName, allBrigadeItems, staff, piecework, calcSalary });

  (manualExpenses || []).filter(item => item.project === projectName).forEach(item => {
    const category = String(item.category || 'other').trim() || 'other';
    result[category] = (result[category] || 0) + Number(item.amount || 0);
  });

  (unexpectedWorksList || [])
    .filter(item => (
      item.projectName === projectName
      && isApprovedEstimateChangeStatus(item.status)
      && item.changeType !== 'Исключение объёма'
      && !item.includedInEstimateId
    ))
    .forEach(item => {
      result.unexpected = (result.unexpected || 0) + Number(item.total || 0);
    });

  (accountablePayments || []).filter(item => item.projectName === projectName).forEach(item => {
    result.accountable = (result.accountable || 0) + Number(item.spentAmount || 0);
  });

  return result;
};

export const projectBudgetSpentSummary = (project, categories = {}) => {
  if (!project) return { works: 0, materials: 0, unexpected: 0, other: 0, total: 0 };
  const total = Object.values(categories || {}).reduce((sum, value) => sum + Number(value || 0), 0);
  const other = total - (categories.works || 0) - (categories.materials || 0) - (categories.unexpected || 0);
  return {
    works: categories.works || 0,
    materials: categories.materials || 0,
    unexpected: categories.unexpected || 0,
    other,
    total,
  };
};

export const workExecutionTotalValue = (work) => (
  Number(work?.executionTotal ?? work?.execution_total ?? 0)
);

export const workCustomerTotalValue = (work) => (
  Number(work?.customerTotal ?? work?.customer_total ?? work?.total ?? 0)
);

export const projectFactSpentValue = ({
  project,
  workJournal = [],
  allBrigadeItems = [],
  materials = [],
} = {}) => {
  if (!project) return { works: 0, materials: 0, total: 0 };
  const journal = (workJournal || [])
    .filter(work => work.project === project.name)
    .reduce((sum, work) => sum + Number(work.total || 0), 0);
  const brigades = (allBrigadeItems || [])
    .filter(item => item.projectName === project.name && Number(item.doneQuantity || 0) > 0)
    .reduce((sum, item) => sum + Number(item.doneQuantity || 0) * Number(item.priceSmeta || 0), 0);
  const works = Math.max(journal, brigades);
  const materialTotal = (materials || [])
    .filter(material => material.project === project.name)
    .reduce((sum, material) => sum + Number(material.quantity || 0) * Number(material.price || 0), 0);
  return { works, materials: materialTotal, total: works + materialTotal };
};

export const buildProjectEconomy = ({
  project,
  projectPlanDone = () => ({ plan: 0, done: 0 }),
  activeEstimatesForProject = () => [],
  estimatePackage = () => '',
  materialControlSummaryForProject = () => ({}),
  projectBudgetSpent = () => ({ works: 0, materials: 0, unexpected: 0, other: 0 }),
  workJournal = [],
} = {}) => {
  if (!project) return null;
  const planDone = projectPlanDone(project);
  const activeEstimates = activeEstimatesForProject(project, 'Заказчик');
  const packages = [...new Set(activeEstimates.map(est => estimatePackage(est)).filter(Boolean))];
  const materialSummary = materialControlSummaryForProject(project.name);
  const spent = projectBudgetSpent(project);
  const projectWorks = (workJournal || []).filter(work => work.project === project.name);
  const confirmedWorks = projectWorks.filter(work => work.status === 'Подтверждено');
  const pendingWorks = projectWorks.filter(work => !work.status || work.status === 'На проверке' || work.status === 'Автоматически из сметы');
  const executionConfirmed = confirmedWorks.reduce((sum, work) => sum + workExecutionTotalValue(work), 0);
  const executionPending = pendingWorks.reduce((sum, work) => sum + workExecutionTotalValue(work), 0);
  const confirmedCustomerFromJournal = confirmedWorks.reduce((sum, work) => sum + workCustomerTotalValue(work), 0);
  const customerClosed = Math.max(Number(planDone.done || 0), confirmedCustomerFromJournal);
  const legacyWorkCost = Math.max(0, Number(spent.works || 0) - executionConfirmed);
  const otherCost = Number(spent.other || 0) + Number(spent.unexpected || 0);
  const currentCost = executionConfirmed + legacyWorkCost + Number(spent.materials || 0) + otherCost;
  const forecastCost = executionConfirmed + executionPending + legacyWorkCost + Number(spent.materials || 0) + otherCost;
  const marginClosed = customerClosed - currentCost;

  return {
    customerPlan: Number(planDone.plan || 0),
    customerClosed,
    customerProgress: Number(planDone.plan || 0) > 0 ? (customerClosed / Number(planDone.plan)) * 100 : 0,
    activeEstimates: activeEstimates.length,
    packages,
    confirmedWorks: confirmedWorks.length,
    pendingWorks: pendingWorks.length,
    executionConfirmed,
    executionPending,
    legacyWorkCost,
    materialPlan: Number(materialSummary?.planSum || 0),
    materialRows: Number(materialSummary?.planRows?.length || 0),
    materialCost: Number(spent.materials || 0),
    otherCost,
    marginClosed,
    marginClosedPct: customerClosed > 0 ? (marginClosed / customerClosed) * 100 : 0,
    marginForecast: Number(planDone.plan || 0) - forecastCost,
  };
};

export const projectRealProgressValue = ({
  project,
  projectPlanDone = () => ({ plan: 0, done: 0 }),
  projectFactSpent = () => ({ total: 0 }),
} = {}) => {
  if (!project) return 0;
  const { plan, done } = projectPlanDone(project);
  if (plan > 0) {
    const pct = (done / plan) * 100;
    return done > 0 && pct < 1 ? 1 : Math.round(pct);
  }
  const budget = Number(project.budget || 0);
  if (budget > 0) {
    const fact = projectFactSpent(project).total;
    return Math.min(100, Math.round((fact / budget) * 100));
  }
  return Number(project.progress || 0);
};
