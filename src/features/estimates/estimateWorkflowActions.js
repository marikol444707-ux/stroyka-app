import {
  activeEstimateFromList,
  applyEstimateActivationState,
  estimateHasLoadedSections,
  estimateUpdatedTs,
  isGlobalEstimateTemplate,
  normalizeEstimateList,
  sameEstimateGroup,
} from '../../utils/estimateUtils';
import { buildEstimateDiffDocumentPayload } from '../../utils/estimateDiffDocumentUtils';
import { signedEstimateChangeTotal } from '../../utils/estimateChangeUtils';
import { estimateChangeAutoDecision } from '../../utils/estimateReviewUtils';
import { fmtMeasure, toNum } from '../../utils/measureUtils';

export const createEstimateWorkflowActions = ({
  API,
  estimatesList = [],
  setEstimatesList,
  setSelectedEstimate,
  estimateReconciliations = [],
  setEstimateReconciliations,
  unexpectedWorksList = [],
  isApprovedEstimateChangeStatus,
  buildEstimateDiffDocContent,
  buildEstimateReconciliationDocContent,
  apiAuthHeaders,
  showPreview,
  refreshData,
  user = {},
  notify = () => {},
  setActiveProjectTab = () => {},
  setActiveTabGroup = () => {},
  setShowForm = () => {},
  setActivePage = () => {},
  setEstimatesTab = () => {},
  queueEstimateDiffReviewTask = async () => {},
  autoReconcileEstimateChanges = async () => {},
  queueEstimateQualityReviewTask = async () => {},
  queueEstimateNormReviewTask = async () => {},
  fetchFn = fetch,
  alertFn = window.alert,
  confirmFn = window.confirm,
  localStorageRef = window.localStorage,
}) => {
  const loadEstimateDetail = async (estimate) => {
    if (!estimate?.id || estimateHasLoadedSections(estimate)) return estimate;
    const token = localStorageRef?.getItem?.('authToken');
    const res = await fetchFn(API + '/estimates/' + encodeURIComponent(estimate.id), token ? {headers:{Authorization:'Bearer '+token}} : undefined);
    if (!res.ok) throw new Error(await res.text());
    const fullRaw = await res.json();
    const normalized = normalizeEstimateList([fullRaw])[0] || fullRaw;
    const merged = {...estimate, ...normalized, sectionsLoaded:true};
    setEstimatesList(prev => (prev||[]).map(e => String(e.id)===String(merged.id) ? {...e, ...merged} : e));
    return merged;
  };

  const openEstimateDetail = async (estimate) => {
    setSelectedEstimate(estimate);
    try {
      const full = await loadEstimateDetail(estimate);
      if (full && full !== estimate) setSelectedEstimate(full);
      return full;
    } catch (err) {
      alertFn('Не удалось загрузить смету: ' + (err?.message || err));
      return estimate;
    }
  };

  const estimateDiffBaseFor = (est) => {
    const group = (estimatesList||[])
      .filter(e=>!isGlobalEstimateTemplate(e) && est?.id!==e.id && sameEstimateGroup(e,est))
      .sort((a,b)=>(estimateUpdatedTs(b)||Number(b.id||0))-(estimateUpdatedTs(a)||Number(a.id||0)));
    return group.find(e=>e.status==='Активная') || group[0] || null;
  };

  const buildEstimateDiffContent = (baseEst, nextEst) => buildEstimateDiffDocContent(buildEstimateDiffDocumentPayload({
    baseEstimate: baseEst,
    nextEstimate: nextEst,
    unexpectedWorksList,
    isApprovedEstimateChangeStatus,
    estimateChangeAutoDecision,
  }));

  const estimateReconciliationsForProject = (projectName) => (estimateReconciliations||[])
    .filter(r=>r.projectName===projectName)
    .sort((a,b)=>Number(b.id||0)-Number(a.id||0));

  const buildEstimateReconciliationContent = (rec) => buildEstimateReconciliationDocContent(rec);

  const loadEstimateReconciliationDetail = async (recOrId) => {
    const id = typeof recOrId === 'object' ? recOrId?.id : recOrId;
    if (!id) return null;
    const cached = typeof recOrId === 'object' && Array.isArray(recOrId.items) ? recOrId : null;
    if (cached) return cached;
    const res = await fetchFn(API+'/estimate-reconciliations/'+id,{headers:apiAuthHeaders()});
    const data = await res.json().catch(()=>({}));
    if (!res.ok) throw new Error(data.detail || 'Не удалось загрузить сверку');
    setEstimateReconciliations(prev=>(prev||[]).map(r=>Number(r.id)===Number(id)?{...r,...data}:r));
    return data;
  };

  const openEstimateReconciliationPreview = async (recOrId) => {
    try {
      const detail = await loadEstimateReconciliationDetail(recOrId);
      if (detail) showPreview(buildEstimateReconciliationContent(detail),'Сверка смет № '+detail.id);
    } catch(e) {
      alertFn(e.message || 'Не удалось открыть сверку');
    }
  };

  const createEstimateReconciliation = async (baseEst, nextEst, options={}) => {
    if (!baseEst?.id || !nextEst?.id) {
      if (!options.silent) alertFn('Не найдена базовая и новая смета для сверки');
      return null;
    }
    try {
      const res = await fetchFn(API+'/estimate-reconciliations',{method:'POST',headers:apiAuthHeaders({'Content-Type':'application/json'}),body:JSON.stringify({baseEstimateId:baseEst.id,nextEstimateId:nextEst.id,notes:options.notes||''})});
      const data = await res.json().catch(()=>({}));
      if (!res.ok) throw new Error(data.detail || 'Не удалось создать сверку');
      const detail = await loadEstimateReconciliationDetail(data.id);
      if (detail) {
        setEstimateReconciliations(prev=>[detail,...(prev||[]).filter(r=>Number(r.id)!==Number(detail.id))]);
        if (!options.silent && options.preview !== false) showPreview(buildEstimateReconciliationContent(detail),'Сверка смет № '+detail.id);
      }
      if (!options.silent) await refreshData();
      return detail || data;
    } catch(e) {
      if (!options.silent) alertFn(e.message || 'Не удалось создать сверку');
      return null;
    }
  };

  const approveEstimateReconciliation = async (rec) => {
    if (!rec?.id) return;
    if (!confirmFn('Утвердить сверку смет № '+rec.id+'? После этого она будет считаться подписанным документом в реестре.')) return;
    const res = await fetchFn(API+'/estimate-reconciliations/'+rec.id,{method:'PUT',headers:apiAuthHeaders({'Content-Type':'application/json'}),body:JSON.stringify({status:'Утверждена'})});
    const data = await res.json().catch(()=>({}));
    if (!res.ok) { alertFn(data.detail || 'Не удалось утвердить сверку'); return; }
    setEstimateReconciliations(prev=>(prev||[]).map(r=>Number(r.id)===Number(rec.id)?{...r,status:'Утверждена',approvedBy:user.name,approvedAt:new Date().toISOString().slice(0,10)}:r));
    await refreshData();
  };

  const estimateChangeTypeForComparisonRow = (row) => row?.status === 'Сверх сметы'
    ? 'Дополнительный объём к строке сметы'
    : row?.status === 'В смете больше'
      ? 'Исключение объёма'
      : '';

  const estimateChangeForComparisonRow = (projectName, row) => {
    const changeType = estimateChangeTypeForComparisonRow(row);
    if (!changeType) return null;
    return (unexpectedWorksList || []).find(u =>
      u.projectName === projectName &&
      u.changeType === changeType &&
      Number(u.estimateId || 0) === Number(row.estimateId || 0) &&
      (u.sectionName || '') === (row.sectionName || '') &&
      (u.estimateItemName || '') === (row.itemName || '') &&
      !['Отклонено', 'Включено в новую смету'].includes(u.status || '')
    ) || null;
  };

  const createEstimateChangeFromComparisonRow = async (project, row) => {
    const changeType = estimateChangeTypeForComparisonRow(row);
    if (!project || !changeType) return;
    const existing = estimateChangeForComparisonRow(project.name, row);
    if (existing) {
      alertFn('Изменение по этой строке уже оформлено: ' + (existing.status || ''));
      setActiveProjectTab('Изменения к смете');
      setActiveTabGroup('work');
      return;
    }
    const unit = row.expectedUnit || row.planUnit || '';
    const deltaQty = row.status === 'Сверх сметы' ? toNum(row.overQty) : toNum(row.shortageQty);
    if (deltaQty <= 0) return;
    const price = toNum(row.price);
    const total = deltaQty * price;
    const reason = row.status === 'Сверх сметы'
      ? 'По обмеру помещений требуется больше, чем указано в активной смете: ' + fmtMeasure(row.measuredQty, unit) + ' против ' + fmtMeasure(row.planQty, row.planUnit) + '.'
      : 'По обмеру помещений требуется меньше, чем указано в активной смете: ' + fmtMeasure(row.measuredQty, unit) + ' против ' + fmtMeasure(row.planQty, row.planUnit) + '.';
    const payload = {
      projectName: project.name,
      description: row.itemName,
      unit,
      quantity: deltaQty,
      price,
      total,
      addedBy: user.name,
      addedByRole: user.role,
      status: 'Ожидает согласования',
      notes: 'Создано из панели «Смета ↔ обмеры помещений». Основание: ' + row.basisLabel + '.',
      changeType,
      estimateId: row.estimateId,
      sectionName: row.sectionName,
      estimateItemName: row.itemName,
      baseQuantity: row.planQty,
      newRequiredQuantity: row.measuredQty,
      deltaQuantity: deltaQty,
      reason,
    };
    const res = await fetchFn(API + '/unexpected-works', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alertFn(data.detail || 'Не удалось оформить изменение');
      return;
    }
    notify('Оформлено изменение к смете: ' + row.itemName, 'unexpected');
    await refreshData();
    setActiveProjectTab('Изменения к смете');
    setActiveTabGroup('work');
    setShowForm(false);
  };

  const includeChangesInNewEstimate = async (project, est, rows) => {
    if (!project || !est || !rows?.length) return;
    const signedTotal = signedEstimateChangeTotal(rows);
    const msg = 'Создать новую активную версию сметы "' + (est.name || '') + '" и включить изменений: ' + rows.length + ' на ' + (signedTotal > 0 ? '+' : '') + Math.round(signedTotal).toLocaleString('ru-RU') + ' ₽?\n\nСтарая смета уйдёт в архив, изменения получат статус "Включено в новую смету" и не будут идти в КС отдельными строками.';
    if (!confirmFn(msg)) return;
    const res = await fetchFn(API + '/estimates/' + est.id + '/include-changes', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({changeIds: rows.map(u => u.id), updatedBy: user.name}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alertFn(data.detail || 'Не удалось включить изменения в смету');
      return;
    }
    await refreshData();
    const next = data.estimate || null;
    if (next) {
      setSelectedEstimate(next);
      setActivePage('estimates');
      setEstimatesTab('list');
    }
    notify('Создана новая версия сметы: ' + (next?.name || ''), 'estimate');
  };

  const setEstimateStatusRemote = async (est, status) => {
    if (!est?.id) return;
    const diffBase = status === 'Активная'
      ? activeEstimateFromList((estimatesList || []).filter(e => !isGlobalEstimateTemplate(e) && e.id !== est.id && sameEstimateGroup(e, est) && e.status === 'Активная'))
      : null;
    const res = await fetchFn(API + '/estimates/' + est.id + '/status', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status}),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alertFn(data.detail || 'Не удалось изменить статус сметы');
      return;
    }
    const updated = {...est, status};
    const nextEstimates = applyEstimateActivationState((estimatesList || []).map(e => e.id === est.id ? updated : e), updated);
    setEstimatesList(nextEstimates);
    setSelectedEstimate(prev => prev && prev.id === est.id ? updated : prev);
    if (status === 'Активная') {
      if (diffBase) {
        await queueEstimateDiffReviewTask(diffBase, updated, 'Смета активирована');
        await autoReconcileEstimateChanges(diffBase, updated, 'Смета активирована');
      }
      await queueEstimateQualityReviewTask(updated, 'Смета активирована');
      await queueEstimateNormReviewTask(updated, 'Смета активирована', nextEstimates);
    }
  };

  const deleteEstimateRemote = async (est) => {
    if (!est?.id) return;
    const title = est.name || 'смету';
    if (!confirmFn('Удалить смету "' + title + '" безвозвратно? Это действие доступно только директору. Если смета уже связана с ЖПР, АОСР, договорными позициями или материалами, сервер не даст удалить ее, чтобы не потерять историю объекта.')) return;
    const res = await fetchFn(API + '/estimates/' + est.id + '?hard=true', {method: 'DELETE'});
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alertFn(data.detail || 'Не удалось удалить смету');
      return;
    }
    setEstimatesList(prev => (prev || []).filter(e => e.id !== est.id));
    setSelectedEstimate(prev => prev && prev.id === est.id ? null : prev);
  };

  return {
    openEstimateDetail,
    estimateDiffBaseFor,
    buildEstimateDiffContent,
    estimateReconciliationsForProject,
    openEstimateReconciliationPreview,
    createEstimateReconciliation,
    approveEstimateReconciliation,
    estimateChangeForComparisonRow,
    createEstimateChangeFromComparisonRow,
    includeChangesInNewEstimate,
    setEstimateStatusRemote,
    deleteEstimateRemote,
  };
};
