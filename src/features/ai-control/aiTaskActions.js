import { parseAiTaskPayload } from '../../utils/aiControlDescriptionUtils';
import { isOpenAiStatus } from '../../utils/statusMetaUtils';

export const createAiTaskActions = ({
  API,
  aiFindings = [],
  aiTasks = [],
  buildEstimateDiffContent,
  estimateDiffBaseFor,
  estimatesList = [],
  navigateTo,
  openEstimateDetail,
  projects = [],
  refreshData,
  setActiveProjectTab,
  setActiveTabGroup,
  setAiFindings,
  setAiTasks,
  setEstimatesTab,
  setExpandedProject,
  setMaterialNormCoverageProject,
  setWarehouseTab,
  showPreview,
  alertFn = window.alert,
  fetchFn = fetch,
}) => {
  const aiFindingsForProject = (projectName) => (aiFindings || []).filter(f => f.projectName === projectName && isOpenAiStatus(f.status));
  const aiTasksForProject = (projectName) => (aiTasks || []).filter(t => t.projectName === projectName && isOpenAiStatus(t.status));

  const generateAiFindingsForProject = async (projectName) => {
    if (!projectName) return;
    const res = await fetchFn(API + '/ai-control/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName, reason: 'manual' }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alertFn(data.detail || 'Не удалось запустить ИИ-контроль');
      return;
    }
    await refreshData();
    alertFn('ИИ-контроль обновлён: замечаний новых ' + (data.created || 0) + ', задач новых ' + (data.tasksCreated || 0) + ', обновлено ' + ((data.updated || 0) + (data.tasksUpdated || 0)) + ', закрыто ' + (data.closed || 0));
  };

  const updateAiFinding = async (id, patch) => {
    await fetchFn(API + '/ai-findings/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    await refreshData();
  };

  const updateAiTask = async (id, patch) => {
    await fetchFn(API + '/ai-tasks/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    await refreshData();
  };

  const patchAiTaskSilent = async (id, patch) => {
    const res = await fetchFn(API + '/ai-tasks/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return null;
    setAiTasks(prev => (prev || []).map(t => Number(t.id) === Number(id) ? data : t));
    return data;
  };

  const patchAiFindingSilent = async (id, patch) => {
    const res = await fetchFn(API + '/ai-findings/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return null;
    setAiFindings(prev => (prev || []).map(f => Number(f.id) === Number(id) ? data : f));
    return data;
  };

  const moveTaskToWorkIfNeeded = async (task) => {
    if (task?.id && ['Новое', 'Принято к исполнению'].includes(task.status || '')) {
      await patchAiTaskSilent(task.id, { status: 'В работе' });
    }
  };

  const openProjectTab = (projectName, tab, group) => {
    const project = (projects || []).find(p => p.name === projectName);
    if (!project) return false;
    navigateTo('projects');
    setExpandedProject(project.id);
    setActiveProjectTab(tab);
    if (group) setActiveTabGroup(group);
    return true;
  };

  const openAiTaskAction = async (task) => {
    const payload = parseAiTaskPayload(task);
    if (payload.type === 'password_reset_request') {
      navigateTo('users');
      await moveTaskToWorkIfNeeded(task);
      return;
    }
    if (payload.type === 'estimate_diff_review') {
      const next = (estimatesList || []).find(e => Number(e.id) === Number(payload.nextEstimateId));
      const base = (estimatesList || []).find(e => Number(e.id) === Number(payload.baseEstimateId)) || (next ? estimateDiffBaseFor(next) : null);
      if (!base || !next) {
        alertFn('Не удалось открыть ведомость: одна из смет не найдена');
        return;
      }
      showPreview(buildEstimateDiffContent(base, next), 'Сопоставительная ведомость');
      await moveTaskToWorkIfNeeded(task);
      return;
    }
    if (payload.type === 'estimate_quality_review') {
      const estimateId = payload.estimateId;
      if (estimateId) {
        const est = (estimatesList || []).find(e => Number(e.id) === Number(estimateId));
        if (est) openEstimateDetail(est);
      }
      setEstimatesTab('list');
      navigateTo('estimates');
      await moveTaskToWorkIfNeeded(task);
      return;
    }
    if (['estimate_norm_review', 'material_norm_coverage'].includes(payload.type)) {
      const projectName = payload.projectName || task.projectName || '';
      const estimateId = payload.estimateId;
      if (projectName) setMaterialNormCoverageProject(projectName);
      if (estimateId) {
        const est = (estimatesList || []).find(e => Number(e.id) === Number(estimateId));
        if (est) openEstimateDetail(est);
      }
      setEstimatesTab('norms');
      navigateTo('estimates');
      await moveTaskToWorkIfNeeded(task);
      return;
    }
    if (payload.type === 'estimate_change_reconcile') {
      openProjectTab(payload.projectName || task.projectName || '', 'Изменения к смете', 'work');
      await moveTaskToWorkIfNeeded(task);
      return;
    }
    if ([
      'material_purchase_review',
      'material_outside_estimate_review',
      'material_writeoff_review',
      'material_norm_over_review',
      'material_without_norm_review',
      'material_transfer_sign_review',
    ].includes(payload.type)) {
      const opened = openProjectTab(payload.projectName || task.projectName || '', 'Материалы', 'object');
      if (!opened) {
        navigateTo('warehouse');
        setWarehouseTab('control');
      }
      await moveTaskToWorkIfNeeded(task);
      return;
    }
    if (['room_measurement_review', 'work_room_link_review'].includes(payload.type)) {
      openProjectTab(
        payload.projectName || task.projectName || '',
        payload.type === 'work_room_link_review' ? 'Производство работ' : 'Помещения',
        payload.type === 'work_room_link_review' ? 'journals' : 'object',
      );
      await moveTaskToWorkIfNeeded(task);
      return;
    }
    if (task?.projectName) {
      openProjectTab(task.projectName, 'ИИ-контроль');
    }
  };

  return {
    aiFindingsForProject,
    aiTasksForProject,
    generateAiFindingsForProject,
    openAiTaskAction,
    patchAiFindingSilent,
    patchAiTaskSilent,
    updateAiFinding,
    updateAiTask,
  };
};
