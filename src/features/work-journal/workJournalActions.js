export const createWorkJournalActions = ({
  API,
  GENERAL_WORK_ROOM_NAME,
  addActivity,
  applyMaterialOverNormReason,
  autoFillNormMaterialsForWork,
  denormalizeMeasure,
  estimatePackage,
  estimateWorkKey,
  estimateWorkMaterials,
  estimateWorkParams,
  estimatesList,
  fmtMeasure,
  isFinanceRole,
  isPersonalMaterialRole,
  materialNameKey,
  materialNormOverrunReason,
  materialWriteoffBlockMessage,
  masterProjectId,
  notify,
  pricelistItems,
  pricelists,
  projects,
  refreshData,
  roomMeasurementCheck,
  roomMeasurementMessage,
  rooms,
  selectedWorks,
  setConfirmAcceptedQty,
  setConfirmComment,
  setConfirmingEntry,
  setEstimateDoneDrafts,
  setEstimateWorkMaterials,
  setEstimateWorkParams,
  setEstimatesList,
  setMasterProjectId,
  setPricelistItems,
  setRejectComment,
  setRejectingEntry,
  setSelectedWorks,
  toNum,
  updateProjectProgress,
  user,
}) => {
  const submitEstimateWorkDone = async (mi, displayQty) => {
    const project = projects.find(p=>p.id===Number(masterProjectId));
    const est = estimatesList.find(e=>Number(e.id)===Number(mi.estId));
    if (!project || !est) return;
    const qty = toNum(mi.quantity);
    const done = toNum(mi.doneQuantity);
    const raw = denormalizeMeasure(displayQty, mi.unit);
    if (raw <= done) { alert('Введите объём больше уже отправленного: сейчас '+fmtMeasure(done,mi.unit)); return; }
    if (qty>0 && raw>qty) { alert('План '+fmtMeasure(qty,mi.unit)+'. Нельзя поставить больше.'); return; }
    const workKey = estimateWorkKey(mi.estId, mi.sectionIdx, mi.itemIdx);
    const estimateItemKey = mi.estimateItemKey || workKey;
    let params = estimateWorkParams[workKey]||{};
    const deltaQty = Math.max(0, raw-done);
    const projectRoomsForWork = rooms.filter(room => room.project === project.name);
    if (!params.roomId && !String(params.roomName || '').trim()) {
      if (projectRoomsForWork.length > 0 && isPersonalMaterialRole()) {
        alert('Выберите помещение для закрытия объёма.');
        return;
      }
      params = { ...params, roomName: GENERAL_WORK_ROOM_NAME };
    }
    const roomCheck = params.roomId ? roomMeasurementCheck(project.name, params.roomId, params.surface||'Стены', deltaQty, mi.unit, mi.name) : null;
    if (roomCheck?.over>0) { alert(roomMeasurementMessage(roomCheck)); return; }
    const currentWorkMaterials = autoFillNormMaterialsForWork(project.name, mi.name, mi.section, deltaQty, mi.unit, estimateWorkMaterials[workKey] || [], {
      ...params,
      workPackage: estimatePackage(est),
    });
    setEstimateWorkMaterials(prev => ({ ...prev, [workKey]: currentWorkMaterials }));
    let usedMats = currentWorkMaterials
      .filter(m=>m.name)
      .map(m=>({name:m.name, quantity:toNum(m.quantity), unit:m.unit||'шт', workPackage:m.workPackage||estimatePackage(est), normQuantity:toNum(m.normQuantity), normSource:m.normSource||'', normRuleId:m.normRuleId||m.ruleId||'', normThicknessMm:m.normThicknessMm||m.thicknessMm||'', autoNorm:!!m.autoNorm, overNorm:toNum(m.normQuantity)>0 && toNum(m.quantity)>toNum(m.normQuantity)*1.1}));
    for (const m of usedMats) {
      if (toNum(m.quantity)<=0) { alert('Укажите количество материала «'+m.name+'» или снимите галочку.'); return; }
    }
    const blockMessage = materialWriteoffBlockMessage(project.name, usedMats);
    if (blockMessage) { alert(blockMessage); return; }
    const overReason = materialNormOverrunReason(project.name, mi.name, usedMats);
    if (overReason === null) return;
    usedMats = applyMaterialOverNormReason(project.name, usedMats, overReason);
    const newSections = est.sections.map((s,si)=>si===mi.sectionIdx?{...s,items:s.items.map((it,ii)=>ii===mi.itemIdx?{...it,doneQuantity:raw}:it)}:s);
    const customerPricePerUnit = toNum(mi.pricePerUnit || mi.price || 0) || (toNum(mi.priceWork || 0) + toNum(mi.priceMaterial || 0));
    const fixedExecutionPrice = toNum(mi.executionPricePerUnit || mi.internalPricePerUnit || mi.masterPricePerUnit || mi.contractorPricePerUnit || mi.executorPricePerUnit);
    const executionCoeff = toNum(mi.executionCoefficient || mi.internalCoefficient || mi.masterCoefficient || mi.contractorCoefficient || mi.executorCoefficient);
    const executionPricePerUnit = fixedExecutionPrice > 0 ? fixedExecutionPrice : (executionCoeff > 0 ? customerPricePerUnit * executionCoeff : 0);
    const executionPriceMode = fixedExecutionPrice > 0 ? 'fixed' : (executionCoeff > 0 ? 'coefficient' : 'not_set');
    if (isPersonalMaterialRole() && executionPricePerUnit <= 0) {
      alert('По этой работе не назначена цена исполнителю. Директор или замдиректора должен задать цену/коэффициент в смете или договорной позиции.');
      return;
    }
    const updated = {
      ...est,
      sections:newSections,
      _workJournalMaterials:{[workKey]:usedMats},
      _workJournalParams:{[workKey]:{
        ...params,
        roomId: params.roomId ? Number(params.roomId) : null,
        roomName: params.roomName || roomCheck?.room?.name || '',
        surface: params.surface || 'Стены',
        workPackage: estimatePackage(est),
        estimateItemName: mi.name,
        estimateItemKey,
        contractItemId: mi.contractItemId || null,
        customerPricePerUnit,
        customerTotal: deltaQty * customerPricePerUnit,
        executionPricePerUnit,
        executionTotal: deltaQty * executionPricePerUnit,
        executionPriceMode,
        photoUrl: params.photoUrl || '',
      }},
    };
    const res = await fetch(API+'/estimates/'+est.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(updated)});
    if (!res.ok) {
      const er = await res.json().catch(()=>({}));
      alert('Не удалось отправить работу: '+(er.detail||res.status));
      return;
    }
    setEstimatesList(prev=>prev.map(e=>Number(e.id)===Number(est.id)?{...est,sections:newSections}:e));
    setEstimateDoneDrafts(prev=>{const next={...prev};delete next[workKey];return next;});
    setEstimateWorkMaterials(prev=>{const next={...prev};delete next[workKey];return next;});
    setEstimateWorkParams(prev=>{const next={...prev};delete next[workKey];return next;});
    await refreshData();
    notify('Работа отправлена в ЖПР: '+mi.name,'work');
    alert('Работа отправлена на проверку. Материалы списаны по выбранным нормам/количествам.');
  };

  const addMasterWorks = async () => {
    const project = projects.find(p=>p.id===Number(masterProjectId));
    if (!project) return;
    const pl = pricelists.find(p=>p.id===project.pricelistId);
    const coeff = pl?pl.coefficient:1.0;
    const now = new Date();
    let hasWork = false;
    const selectedEntries = Object.entries(selectedWorks).filter(([itemId,workData])=>{
      const item = pricelistItems.find(i=>i.id===Number(itemId));
      return item && workData.quantity && toNum(workData.quantity)>0;
    });
    if (!selectedEntries.length) { alert('Введите количество хотя бы для одной работы'); return; }
    const projectRoomsForWork = rooms.filter(room => room.project === project.name);
    const normalizedSelectedEntries = selectedEntries.map(([itemId, workData]) => {
      if (!workData.roomId && !String(workData.roomName || '').trim() && projectRoomsForWork.length === 0) {
        return [itemId, { ...workData, roomName: GENERAL_WORK_ROOM_NAME }];
      }
      return [itemId, workData];
    });
    const plannedUsage = {};
    for (const [itemId, workData] of normalizedSelectedEntries) {
      const item = pricelistItems.find(i=>i.id===Number(itemId));
      if (!workData.roomId && !String(workData.roomName || '').trim()) {
        if (projectRoomsForWork.length > 0 && isPersonalMaterialRole()) {
          alert('Выберите помещение для работы «'+item.name+'».');
          return;
        }
      }
      const roomCheck = workData.roomId ? roomMeasurementCheck(project.name, workData.roomId, workData.surface||'Стены', workData.quantity, item.unit, item.name) : null;
      if (roomCheck?.over>0) { alert(roomMeasurementMessage(roomCheck)); return; }
      for (const m of (workData.materials||[]).filter(mm=>mm.name)) {
        const qty = toNum(m.quantity);
        if (qty<=0) { alert('Укажите количество материала «'+m.name+'» для работы «'+item.name+'» или снимите галочку.'); return; }
        const key = materialNameKey(m.name);
        if (!plannedUsage[key]) plannedUsage[key] = {name:m.name, unit:m.unit||'шт', quantity:0};
        plannedUsage[key].quantity += qty;
      }
    }
    const blockMessage = materialWriteoffBlockMessage(project.name, Object.values(plannedUsage));
    if (blockMessage) { alert(blockMessage); return; }
    const overrunReasons = {};
    for (const [itemId, workData] of normalizedSelectedEntries) {
      const item = pricelistItems.find(i=>i.id===Number(itemId));
      if (!item) continue;
      const overReason = materialNormOverrunReason(project.name, item.name, workData.materials||[]);
      if (overReason === null) return;
      if (overReason) overrunReasons[itemId] = overReason;
    }
    for (const [itemId,workData] of normalizedSelectedEntries) {
      const item = pricelistItems.find(i=>i.id===Number(itemId));
      if (!item) continue;
      hasWork = true;
      const ppu = item.price*coeff;
      const workQty = toNum(workData.quantity);
      const total = workQty*ppu;
      const reason = overrunReasons[itemId] || '';
      const usedMats=(workData.materials||[]).filter(m=>m.name&&toNum(m.quantity)>0).map(m=>{const over=toNum(m.normQuantity)>0&&toNum(m.quantity)>toNum(m.normQuantity)*1.1;return {name:m.name,quantity:toNum(m.quantity),unit:m.unit||'шт',workPackage:m.workPackage||'Прайс',normQuantity:toNum(m.normQuantity),normSource:m.normSource||'',normRuleId:m.normRuleId||m.ruleId||'',normThicknessMm:m.normThicknessMm||m.thicknessMm||'',autoNorm:!!m.autoNorm,overNorm:over,overNormReason:over?reason:''};});
      const wjRes=await fetch(API+'/work-journal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({masterId:user.id,masterName:user.name,project:project.name,description:item.name,unit:item.unit,quantity:workQty,pricePerUnit:ppu,total,customerPricePerUnit:ppu,customerTotal:total,executionPricePerUnit:ppu,executionTotal:total,executionPriceMode:'pricelist',date:now.toISOString().split('T')[0],comment:workData.comment||'',photoUrl:workData.photoUrl||'',materialsUsed:usedMats,workPackage:'Прайс',roomId:workData.roomId?Number(workData.roomId):null,roomName:workData.roomName||'',surface:workData.surface||'Стены',estimateItemName:item.name})});
      if(!wjRes.ok){const er=await wjRes.json().catch(()=>({}));alert('Не удалось отправить работу: '+(er.detail||'ошибка'));return;}
    }
    if (!hasWork) { alert('Введите количество хотя бы для одной работы'); return; }
    notify(user.name+' отправил работы','work');
    await refreshData(); setSelectedWorks({}); setMasterProjectId(''); setPricelistItems([]);
    alert('Работы отправлены на проверку!');
  };

  const openConfirmModal = (e) => {
    const fallbackPpu = (Number(e.executionPricePerUnit||0)===0 && Number(e.quantity||0)>0) ? (Number(e.executionTotal||0)/Number(e.quantity||0)) : Number(e.executionPricePerUnit||0);
    setConfirmingEntry({...e, _ppu: fallbackPpu});
    setConfirmAcceptedQty(String(e.quantity||''));
    setConfirmComment('');
  };

  const confirmJ = async (e, acceptedQty, comment) => {
    const planQty = toNum(e.quantity||0);
    const accepted = (acceptedQty===undefined||acceptedQty===null||acceptedQty==='')?planQty:toNum(acceptedQty);
    const ppu = Number(e._ppu||e.executionPricePerUnit||0) || (Number(e.executionTotal||0)/Math.max(1, planQty));
    const customerPpu = Number(e.customerPricePerUnit||0) || (Number(e.customerTotal||0)/Math.max(1, planQty));
    const newTotal = Math.round(accepted * ppu);
    const newCustomerTotal = Math.round(accepted * customerPpu);
    const body = {
      status:'Подтверждено',
      confirmedBy:user.name,
      confirmedAt:new Date().toISOString().split('T')[0],
      quantity: accepted,
    };
    if (isFinanceRole) {
      body.total = newTotal;
      body.pricePerUnit = ppu;
      body.executionPricePerUnit = ppu;
      body.executionTotal = newTotal;
      body.customerPricePerUnit = customerPpu;
      body.customerTotal = newCustomerTotal;
    }
    if(comment) body.comment = comment;
    await fetch(API+'/work-journal/'+e.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    await refreshData();
    await updateProjectProgress(e.project||"");
    setConfirmingEntry(null); setConfirmAcceptedQty(''); setConfirmComment('');
    const msg = (accepted<planQty)?('Принято '+accepted+' из '+planQty+' '+(e.unit||'')+' · '+e.description):'Работа подтверждена: '+e.description;
    notify(msg,'work'); addActivity(msg);
  };

  const rejectJ = async (e,c) => {
    await fetch(API+'/work-journal/'+e.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонено',confirmedBy:user.name,comment:c||''})});
    await refreshData(); setRejectingEntry(null); setRejectComment('');
  };

  return {
    addMasterWorks,
    confirmJ,
    openConfirmModal,
    rejectJ,
    submitEstimateWorkDone,
  };
};
