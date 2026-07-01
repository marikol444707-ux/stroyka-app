import {
  estimateHasLoadedSections,
  estimateUpdatedTs,
  isGlobalEstimateTemplate,
  normalizeEstimateList,
  sameEstimateGroup,
} from '../../utils/estimateUtils';
import { buildEstimateDiffDocumentPayload } from '../../utils/estimateDiffDocumentUtils';
import { estimateChangeAutoDecision } from '../../utils/estimateReviewUtils';

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

  return {
    openEstimateDetail,
    estimateDiffBaseFor,
    buildEstimateDiffContent,
    estimateReconciliationsForProject,
    openEstimateReconciliationPreview,
    createEstimateReconciliation,
    approveEstimateReconciliation,
  };
};
