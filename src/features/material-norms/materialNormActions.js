import { fmtMeasure, toNum } from '../../utils/measureUtils';
import {
  EMPTY_MATERIAL_NORM_FORM,
  materialNormCanCreateSupply,
  materialTitleForNormRule,
  normListToText,
} from '../../utils/materialNormUtils';
import {
  autoFillNormMaterialsForWorkRows,
  buildBatchMaterialNormSupplyRequestPayloads,
  buildMaterialNormPayload,
  buildMaterialNormSupplyRequestPayload,
  materialNormSupplyRequestExistsForRow,
} from '../../utils/materialNormWorkflowUtils';

export const createMaterialNormActions = ({
  API,
  user,
  projects = [],
  supplyRequests = [],
  materialNormPreviewSuggestions = [],
  materialNormSuggestions = [],
  materialNormCoverageProject = '',
  newMaterialNorm,
  editingMaterialNormId,
  estimatesTab,
  isActiveSupplyRequestStatus,
  materialRowsAvailableForWork,
  materialNormForWork,
  capMaterialWriteoffQty,
  materialNameKey,
  visibleActiveProjects,
  canEditMaterialNormsForUser,
  canCreateSupplyRequestFromNormForUser,
  setSupplyRequests,
  setMaterialNormNotice,
  setNewMaterialNorm,
  setEditingMaterialNormId,
  setEstimatesTab,
  setMaterialNormSuggestionLoading,
  setMaterialNormPreviewSuggestions,
  setEstimatesList,
  setSelectedEstimate,
  notify,
  refreshData,
  navigateTo,
  fetchFn = fetch,
  alertFn = window.alert,
  confirmFn = window.confirm,
  promptFn = window.prompt,
}) => {
  const materialNormSupplyRequestExists = (row) => materialNormSupplyRequestExistsForRow({
    row,
    supplyRequests,
    isActiveSupplyRequestStatus,
  });

  const canEditMaterialNorms = () => canEditMaterialNormsForUser(user);
  const canCreateSupplyRequestFromNorm = () => canCreateSupplyRequestFromNormForUser(user);

  const createSupplyRequestFromNormCoverage = async (row) => {
    if (!materialNormCanCreateSupply(row)) return;
    if (!canCreateSupplyRequestFromNorm()) { alertFn('У вашей роли нет права создать заявку снабжения'); return; }
    if (materialNormSupplyRequestExists(row) && !confirmFn('По этой строке нормы уже есть активная заявка. Создать ещё одну?')) return;
    const defaultName = row.materialName || materialTitleForNormRule(row.rule);
    const name = promptFn('Материал для заявки снабжения:', defaultName);
    if (name === null) return;
    const cleanName = name.trim();
    if (!cleanName) { alertFn('Название материала не может быть пустым'); return; }
    const defaultQty = toNum(row.shortageQty || row.requiredQty);
    const qtyRaw = promptFn('Количество к заявке:', String(defaultQty || ''));
    if (qtyRaw === null) return;
    const qty = toNum(qtyRaw);
    if (qty <= 0) { alertFn('Количество должно быть больше 0'); return; }
    const payload = buildMaterialNormSupplyRequestPayload({row, materialName:cleanName, quantity:qty, user});
    const unit = payload.unit;
    const res = await fetchFn(API+'/supply-requests', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    });
    const data = await res.json().catch(()=>({}));
    if (!res.ok) { alertFn(data.detail || 'Не удалось создать заявку снабжения'); return; }
    setSupplyRequests(prev=>data?.id?[data,...(prev||[]).filter(r=>Number(r.id)!==Number(data.id))]:(prev||[]));
    notify('Создана заявка снабжения: '+cleanName+' — '+fmtMeasure(qty,unit), 'supply');
    setMaterialNormNotice({tone:'success',title:'Заявка создана',text:'Потребность отправлена в снабжение. В смете строка пока не менялась: её можно добавить отдельно кнопкой «Материал».'});
    await refreshData();
  };

  const createBatchSupplyRequestFromNormCoverage = async (rows=[]) => {
    if (!canCreateSupplyRequestFromNorm()) { alertFn('У вашей роли нет права создать заявку снабжения'); return; }
    const candidates = (rows||[]).filter(materialNormCanCreateSupply);
    const fresh = candidates.filter(r=>!materialNormSupplyRequestExists(r));
    if (!fresh.length) {
      alertFn(candidates.length ? 'По всем недостающим материалам уже есть активные заявки' : 'Нет строк для заявки');
      return;
    }
    if (!confirmFn('Создать одну пакетную заявку снабжения по '+fresh.length+' незаявленным строкам?')) return;
    const payloads = buildBatchMaterialNormSupplyRequestPayloads({
      rows: fresh,
      user,
      materialNameKey,
    });
    if (!payloads.length) { alertFn('Не удалось собрать позиции заявки'); return; }
    const created = [];
    for (const {requestPackage, payload} of payloads) {
      const res = await fetchFn(API+'/supply-requests', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(payload)
      });
      const data = await res.json().catch(()=>({}));
      if (!res.ok) { alertFn((data.detail || 'Не удалось создать пакетную заявку')+' · раздел '+requestPackage); return; }
      if (data?.id) created.push(data);
    }
    if (created.length) setSupplyRequests(prev=>[...created,...(prev||[]).filter(r=>!created.some(n=>Number(n.id)===Number(r.id)))]);
    const itemsCount = payloads.reduce((sum, item)=>sum+(item.items||[]).length, 0);
    notify('Создано заявок снабжения: '+created.length+' · позиций '+itemsCount, 'supply');
    setMaterialNormNotice({tone:'success',title:'Пакетные заявки созданы',text:'В снабжение отправлено '+itemsCount+' позиций по '+fresh.length+' строкам норм. Заявки разделены по пакетам работ.'});
    await refreshData();
  };

  const autoFillNormMaterialsForWork = (projectName, workName, sectionName, workQty, workUnit, currentMaterials=[], params={}) => autoFillNormMaterialsForWorkRows({
    projectName,
    workName,
    sectionName,
    workQty,
    workUnit,
    currentMaterials,
    params,
    materialRowsAvailableForWork,
    materialNormForWork,
    capMaterialWriteoffQty,
    materialNameKey,
  });

  const materialNormPayload = () => buildMaterialNormPayload(newMaterialNorm);

  const resetMaterialNormForm = () => {
    setNewMaterialNorm(EMPTY_MATERIAL_NORM_FORM);
    setEditingMaterialNormId(null);
  };

  const editMaterialNorm = (rule) => {
    setEditingMaterialNormId(rule.id);
    setNewMaterialNorm({
      ruleKey: rule.ruleKey || rule.id || '',
      name: rule.name || materialTitleForNormRule(rule),
      workText: normListToText(rule.work),
      blockWorkText: normListToText(rule.blockWork),
      materialText: normListToText(rule.material),
      workUnit: rule.workUnit || 'м2',
      materialUnit: rule.materialUnit || 'кг',
      qtyPerUnit: String(rule.qtyPerUnit || ''),
      thicknessBaseMm: rule.thicknessBaseMm ? String(rule.thicknessBaseMm) : '',
      defaultThicknessMm: rule.defaultThicknessMm ? String(rule.defaultThicknessMm) : '',
      label: rule.label || '',
    });
    if (estimatesTab !== 'norms') setEstimatesTab('norms');
  };

  const saveMaterialNorm = async () => {
    if (!canEditMaterialNorms()) return;
    const payload = materialNormPayload();
    if (!payload.name || !payload.work.length || !payload.material.length || payload.qtyPerUnit<=0) {
      alertFn('Заполни название, ключевые слова работы, материал и расход больше 0');
      return;
    }
    const path = editingMaterialNormId ? '/material-norms/'+editingMaterialNormId : '/material-norms';
    const method = editingMaterialNormId ? 'PUT' : 'POST';
    const res = await fetchFn(API+path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if (!res.ok) {
      const data = await res.json().catch(()=>({detail:'Не удалось сохранить норму'}));
      alertFn(data.detail || 'Не удалось сохранить норму');
      return;
    }
    resetMaterialNormForm();
    await refreshData();
  };

  const disableMaterialNorm = async (id) => {
    if (!canEditMaterialNorms() || !id) return;
    if (!confirmFn('Отключить норму? Она пропадёт из расчётов, но история останется.')) return;
    const res = await fetchFn(API+'/material-norms/'+id,{method:'DELETE'});
    if (!res.ok) {
      alertFn('Не удалось отключить норму');
      return;
    }
    await refreshData();
  };

  const activeMaterialNormSuggestions = () => [
    ...(materialNormPreviewSuggestions||[]),
    ...(materialNormSuggestions||[]).filter(s=>!['Принята','Отклонена'].includes(s.status||''))
  ];

  const generateMaterialNormSuggestions = async (opts={}) => {
    if (!canEditMaterialNorms()) return;
    const dryRun = !!opts.dryRun;
    let projectName = opts.projectName || '';
    const defaultProjectName = materialNormCoverageProject || visibleActiveProjects(projects||[])[0]?.name || '';
    if (dryRun && !projectName) {
      projectName = promptFn('Объект для безопасного предпросмотра норм:', defaultProjectName);
      if (projectName === null) return;
      projectName = projectName.trim();
    }
    if (!dryRun && !projectName) {
      projectName = promptFn('Объект для AI-проверки норм (пусто — все объекты):', defaultProjectName);
      if (projectName === null) return;
      projectName = projectName.trim();
    }
    setMaterialNormSuggestionLoading(true);
    setMaterialNormNotice(null);
    try {
      const payload = dryRun ? {dryRun:true,useAi:false,projectName} : (projectName ? {projectName} : {});
      const res = await fetchFn(API+'/material-norm-suggestions/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data = await res.json().catch(()=>({}));
      if (!res.ok) throw new Error(data.detail || 'Не удалось проверить нормы');
      const scopeText = projectName ? 'Объект: '+projectName : 'Все объекты';
      const d = data.diagnostics || {};
      const diagnosticText = 'Проверено: смет '+(d.activeCustomerEstimates||0)+', работ '+(d.estimateWorks||0)+', материалов '+(d.estimateMaterials||0)+', по родителю '+(d.estimateMaterialsLinkedByParent||0)+', по поиску '+(d.estimateMaterialsLinkedByHeuristic||0)+', покрыто нормами '+(d.estimateMaterialsCoveredByNorm||0)+', без работы '+(d.estimateMaterialsWithoutCandidateWork||0)+', ЖПР '+(d.workJournalRows||0)+', списаний '+(d.workJournalMaterialFacts||0);
      if (dryRun) {
        setMaterialNormPreviewSuggestions((data.suggestions||[]).map((s,i)=>({...s,id:s.id||('preview-'+i),status:'Предпросмотр',previewOnly:true})));
        setMaterialNormNotice({
          tone:'info',
          title:'Предпросмотр норм',
          text:'Найдено '+(data.total||0)+' · '+scopeText+' · '+diagnosticText+' · без сохранения · без внешнего ИИ'
        });
      } else {
        setMaterialNormPreviewSuggestions([]);
        await refreshData();
        setMaterialNormNotice({
          tone:'success',
          title:'AI-проверка норм',
          text:'Найдено '+(data.total||0)+', новых '+(data.created||0)+', обновлено '+(data.updated||0)+' · '+scopeText+' · '+diagnosticText+(data.aiUsed?' · YandexGPT подключён':' · без внешнего ИИ')
        });
      }
    } catch(e) {
      alertFn(e.message || 'Не удалось проверить нормы');
    } finally {
      setMaterialNormSuggestionLoading(false);
    }
  };

  const buildMaterialNormAcceptRequest = (options={}) => {
    if (!Object.prototype.hasOwnProperty.call(options || {}, 'qtyPerUnit')) return {};
    const qtyPerUnit = toNum(String(options.qtyPerUnit ?? '').replace(',', '.'));
    if (!(qtyPerUnit > 0)) {
      alertFn('Укажите норму расхода больше 0');
      return null;
    }
    return {
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({qtyPerUnit})
    };
  };

  const acceptMaterialNormSuggestion = async (id, options={}) => {
    if (!canEditMaterialNorms() || !id) return;
    const request = buildMaterialNormAcceptRequest(options);
    if (!request) return;
    if (!confirmFn('Принять предложение и записать норму в справочник?')) return;
    const res = await fetchFn(API+'/material-norm-suggestions/'+id+'/accept',{method:'POST',...request});
    const data = await res.json().catch(()=>({}));
    if (!res.ok) {
      alertFn(data.detail || 'Не удалось принять предложение');
      return;
    }
    await refreshData();
  };

  const acceptMaterialNormSuggestionAsOverride = async (id, options={}) => {
    if (!canEditMaterialNorms() || !id) return;
    const request = buildMaterialNormAcceptRequest(options);
    if (!request) return;
    if (!confirmFn('Принять как поправку объекта? Базовая норма компании не изменится.')) return;
    const res = await fetchFn(API+'/material-norm-suggestions/'+id+'/accept-override',{method:'POST',...request});
    const data = await res.json().catch(()=>({}));
    if (!res.ok) {
      alertFn(data.detail || 'Не удалось сохранить поправку объекта');
      return;
    }
    setMaterialNormNotice({tone:'success',title:'Поправка объекта сохранена',text:'Базовая норма не изменена. Поправка будет применяться при расчётах по этому объекту.'});
    await refreshData();
  };

  const createEstimateFromNormSuggestions = async (withSupplyRequest=false) => {
    if (!canEditMaterialNorms()) return;
    const defaultProjectName = materialNormCoverageProject || visibleActiveProjects(projects||[])[0]?.name || '';
    let projectName = promptFn('Для какого объекта сформировать черновик материалов по нормам?', defaultProjectName);
    if (projectName === null) return;
    projectName = projectName.trim();
    if (!projectName) return;
    setMaterialNormSuggestionLoading(true);
    setMaterialNormNotice(null);
    try {
      const res = await fetchFn(API+'/material-norm-suggestions/create-estimate',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({projectName,minConfidence:0.75,status:'Черновик',createSupplyRequest:!!withSupplyRequest})
      });
      const data = await res.json().catch(()=>({}));
      if (!res.ok) throw new Error(data.detail || 'Не удалось сформировать черновик сметы');
      const created = {
        id:data.id,
        projectName:data.projectName,
        name:data.name,
        version:data.version||'',
        sections:data.sections||[],
        smetaType:data.smetaType||'Материалы',
        workPackage:data.workPackage||'Доп. материалы',
        status:data.status||'Черновик'
      };
      setEstimatesList(prev=>[created,...(prev||[]).filter(e=>Number(e.id)!==Number(created.id))]);
      if (data.supplyRequest?.id) {
        setSupplyRequests(prev=>[data.supplyRequest,...(prev||[]).filter(r=>Number(r.id)!==Number(data.supplyRequest.id))]);
      }
      setSelectedEstimate(created);
      setMaterialNormNotice({
        tone:'success',
        title:data.supplyRequest?.id?'Черновик сметы и заявка созданы':'Черновик сметы создан',
        text:'Строк: '+(data.items||0)+', с ценой '+(data.priced||0)+', без цены '+(data.missingPrice||0)+', сумма '+Number(data.total||0).toLocaleString('ru-RU')+' ₽. '+(data.supplyRequest?.id?'Заявка снабжения #'+data.supplyRequest.id+' создана в статусе «Новая». ':'')+'Черновик не меняет активную смету.'
      });
      await refreshData();
      navigateTo('estimates');
    } catch(e) {
      alertFn(e.message || 'Не удалось сформировать черновик сметы');
    } finally {
      setMaterialNormSuggestionLoading(false);
    }
  };

  const rejectMaterialNormSuggestion = async (id) => {
    if (!canEditMaterialNorms() || !id) return;
    const res = await fetchFn(API+'/material-norm-suggestions/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонена'})});
    if (!res.ok) {
      alertFn('Не удалось отклонить предложение');
      return;
    }
    await refreshData();
  };

  const createTaskFromMaterialNormSuggestion = async (id) => {
    if (!canEditMaterialNorms() || !id) return;
    const res = await fetchFn(API+'/material-norm-suggestions/'+id+'/task',{method:'POST'});
    const data = await res.json().catch(()=>({}));
    if (!res.ok) {
      alertFn(data.detail || 'Не удалось создать поручение');
      return;
    }
    await refreshData();
    alertFn('Поручение создано в ИИ-контроле объекта');
  };

  return {
    materialNormSupplyRequestExists,
    createSupplyRequestFromNormCoverage,
    createBatchSupplyRequestFromNormCoverage,
    autoFillNormMaterialsForWork,
    canEditMaterialNorms,
    canCreateSupplyRequestFromNorm,
    materialNormPayload,
    resetMaterialNormForm,
    editMaterialNorm,
    saveMaterialNorm,
    disableMaterialNorm,
    activeMaterialNormSuggestions,
    generateMaterialNormSuggestions,
    buildMaterialNormAcceptRequest,
    acceptMaterialNormSuggestion,
    acceptMaterialNormSuggestionAsOverride,
    createEstimateFromNormSuggestions,
    rejectMaterialNormSuggestion,
    createTaskFromMaterialNormSuggestion,
  };
};
