import {
  buildInternalWarehouseReceiptNumber,
  buildScanDraftInvoiceNumber,
} from '../../utils/accountingInvoices';
import {
  createIssueToolForm,
  createToolForm,
  createWarehouseInvoiceForm,
  createWarehouseMovementForm,
} from './warehouseInitialForms';

import {matchesMovementScope, movementRequest, newMovementId} from './movementRecovery';

const movementDrafts = new WeakMap();
const activeMovementScopes = new Set();
const prepareMovementDraft = (draft, user) => {
  if (movementDrafts.has(draft)) return movementDrafts.get(draft);
  const prepared = {draftId: newMovementId(), commands: (draft.selectedMaterials || []).map(item => ({
    commandId: newMovementId(), materialName: item.name, fromLocation: draft.fromLocation,
    toLocation: draft.toLocation, quantity: Number(item.quantity), unit: item.unit,
    workPackage: item.workPackage || item.work_package || draft.workPackage || '',
    date: new Date().toISOString().split('T')[0], createdBy: user.name, notes: draft.notes,
    invoiceId: item.invoiceId ?? null, invoiceLineIndex: item.invoiceLineIndex ?? null,
  }))};
  movementDrafts.set(draft, prepared);
  return prepared;
};

export const createWarehouseCrudActions = ({
  API,
  addActivity,
  calcVat,
  createInvoiceControlReviewTasksForInvoice,
  editingItem,
  getProjectWorkPackageOptions,
  issueToolData,
  newInvoice,
  newMovement,
  movementScope,
  isMovementScopeCurrent = () => false,
  newTool,
  notify,
  projects,
  refreshData,
  returnToolCondition,
  setEditingItem,
  setIssueToolData,
  setNewInvoice,
  setNewMovement,
  setNewTool,
  setReturnToolCondition,
  setShowReceiveDialog,
  setShowForm,
  setShowIssueToolModal,
  setShowReturnToolModal,
  setShowScanInvoice,
  suppliers,
  user,
}) => {
  const openReceiveInvoice = (preselectedLocation, options = {}) => {
    const assignedProjectNames = [
      ...(Array.isArray(user?.assignedProjects) ? user.assignedProjects : []),
      ...(Array.isArray(user?.assigned_projects) ? user.assigned_projects : []),
      user?.projectName,
      user?.project_name,
      user?.project,
    ].map((project) => {
      if (!project) return '';
      if (typeof project === 'string') return project;
      return project.name || project.projectName || project.project_name || '';
    }).map((project) => String(project).trim()).filter(Boolean);
    const assignedProjectSet = new Set(assignedProjectNames);
    let location = preselectedLocation || '';
    if (!location && user?.role === 'прораб') {
      const projectFromList = assignedProjectNames.length
        ? (projects || []).find((project) => project?.name && !project.archived && project.status !== 'Завершён' && assignedProjectSet.has(project.name))
        : null;
      location = projectFromList?.name || assignedProjectNames[0] || '';
    }
    if (newInvoice?.originalUrls?.length && !newInvoice.receiptCompleted
        && (!preselectedLocation || newInvoice.location === preselectedLocation)) {
      setShowScanInvoice(true);
      return;
    }
    const warehouseTarget = location && location !== 'Основной склад' ? 'object' : 'main';
    setNewInvoice({
      ...createWarehouseInvoiceForm(),
      receiptDraftId: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      date:new Date().toISOString().split('T')[0],
      acceptedBy:user?.name||'',
      location,
      project:warehouseTarget === 'object' ? location : '',
      warehouseTarget,
      sourceType:warehouseTarget === 'object' ? 'manual_project_invoice' : 'manual_main_invoice',
      supplier:'',
      totalWithVat:0
    });
    if (options.scanFirst) {
      setShowScanInvoice(true);
      return;
    }
    setShowReceiveDialog(true);
  };

  const saveInvoiceNew = async () => {
    const isScannedInvoice = String(newInvoice.sourceType || '').startsWith('scan_') || Boolean(newInvoice.scanDocumentType || newInvoice.scanWarnings);
    if (!newInvoice.location) { alert('Выберите куда оприходовать (основной склад или объект)'); return false; }
    const inventoryOnlyMainReceipt = newInvoice.location === 'Основной склад' && newInvoice.inventoryOnly === true;
    const invoiceNumber = String(newInvoice.number || '').trim()
      || (inventoryOnlyMainReceipt ? buildInternalWarehouseReceiptNumber() : '')
      || (isScannedInvoice ? buildScanDraftInvoiceNumber() : '');
    if (!invoiceNumber || newInvoice.items.filter(i=>i.name&&i.quantity).length===0) {
      alert(inventoryOnlyMainReceipt ? 'Добавьте материалы' : 'Заполните номер накладной и материалы');
      return false;
    }
    const supplierId = inventoryOnlyMainReceipt ? null : (Number(newInvoice.supplierId) || null);
    const selectedSupplier = supplierId
      ? suppliers.find(s=>s.id===supplierId)
      : null;
    const freeTextSupplierName = newInvoice.isNewSupplier
      ? (newInvoice.supplier || newInvoice.newSupplierName)
      : '';
    const resolvedSupplierName = inventoryOnlyMainReceipt
      ? ''
      : String(
        selectedSupplier?.name
        || freeTextSupplierName
        || '',
      ).trim();
    if (!inventoryOnlyMainReceipt && newInvoice.location === 'Основной склад' && !supplierId && !resolvedSupplierName) {
      alert('Выберите поставщика или включите режим «Без поставщика и оплаты»');
      return false;
    }
    const invoiceProject = newInvoice.location !== 'Основной склад' ? newInvoice.location : '';
    const invoicePackages = invoiceProject ? getProjectWorkPackageOptions(invoiceProject) : [];
    const defaultWorkPackage = newInvoice.workPackage || (invoicePackages.length === 1 ? invoicePackages[0] : '');
    const validItems = newInvoice.items
      .filter(i=>i.name&&i.quantity)
      .map(i=>({...i, workPackage:i.workPackage || i.work_package || defaultWorkPackage}));
    const rowsTotal = validItems.reduce((s,i)=>s+(Number(i.lineTotal||0)||Number(i.quantity)*Number(i.price||0)),0);
    const declaredTotal = Number(newInvoice.totalWithVat||0);
    const declaredBase = Number(newInvoice.totalBase||0);
    const declaredVat = Number(newInvoice.totalVat||0);
    const totalBefore = declaredTotal > 0 ? declaredTotal : (declaredBase > 0 && declaredVat > 0 ? declaredBase + declaredVat : rowsTotal);
    const calculatedVat = calcVat(totalBefore, newInvoice.vat);
    const inferredVat = declaredVat > 0 ? declaredVat : (declaredTotal > 0 && declaredBase > 0 ? Math.max(0, declaredTotal - declaredBase) : 0);
    const vatCalc = {
      base: declaredBase > 0 ? declaredBase : calculatedVat.base,
      vat: inferredVat > 0 ? inferredVat : calculatedVat.vat,
      total: totalBefore,
    };
    const photoUrls = Array.isArray(newInvoice.photoUrls) && newInvoice.photoUrls.length ? newInvoice.photoUrls : (Array.isArray(newInvoice.photos) ? newInvoice.photos : []);
    const photoUrl = photoUrls.length > 0 ? photoUrls[0] : (newInvoice.photoUrl || '');
    const warehouseTarget = newInvoice.warehouseTarget || (invoiceProject ? 'object' : 'main');
    const selectedAction = inventoryOnlyMainReceipt
      ? 'receive_stock_without_supplier'
      : (newInvoice.selectedAction || 'receive_to_warehouse');
    const sourceType = inventoryOnlyMainReceipt
      ? 'manual_main_receipt'
      : (newInvoice.sourceType || (invoiceProject ? 'manual_project_invoice' : 'manual_main_invoice'));
    const materialMatch = validItems.map((item, index) => ({
      row:index+1,
      name:item.name || '',
      quantity:Number(item.quantity || 0) || 0,
      unit:item.unit || '',
      workPackage:item.workPackage || item.work_package || '',
      estimateMatched:Boolean(item.estimateMaterialId || item.estimateItemId || item.workPackage || item.work_package),
      needsReview:invoiceProject ? !(item.workPackage || item.work_package) : false,
    }));
    const inv = {
      id:Date.now(),
      number:invoiceNumber,
      date:newInvoice.date,
      supplierId:inventoryOnlyMainReceipt ? null : supplierId,
      supplierName:inventoryOnlyMainReceipt ? '' : resolvedSupplierName,
      supplierInn:inventoryOnlyMainReceipt ? '' : (newInvoice.supplierInn || ''),
      supplierKpp:inventoryOnlyMainReceipt ? '' : (newInvoice.supplierKpp || ''),
      supplierOgrn:inventoryOnlyMainReceipt ? '' : (newInvoice.supplierOgrn || ''),
      acceptedBy:newInvoice.acceptedBy||user.name,
      location:newInvoice.location,
      project:invoiceProject,
      vat:newInvoice.vat,
      photoUrl,
      photos:photoUrls,
      photoUrls,
      pagesCount:newInvoice.pagesCount||photoUrls.length||1,
      items:validItems,
      totalBase:vatCalc.base,
      totalVat:vatCalc.vat,
      totalWithVat:vatCalc.total,
      status:'Принята',
      addedBy:user.name,
      warehouseTarget,
      inventoryOnly:inventoryOnlyMainReceipt,
      accountingRequired:!inventoryOnlyMainReceipt,
      syncSupplierInvoice:!inventoryOnlyMainReceipt,
      selectedAction,
      sourceType,
      sourceId:newInvoice.sourceId||null,
      materialMatch,
      receiptDocument: newInvoice.receiptDocument,
      originalUrls: newInvoice.originalUrls || photoUrls,
      physicalReceiptConfirmed: newInvoice.physicalReceiptConfirmed === true,
      newDocumentConfirmed: newInvoice.newDocumentConfirmed === true,
    };
    const savedInv = inv;
    const invoiceRes = await fetch(API+'/warehouse-invoices',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(savedInv)});
    if (!invoiceRes.ok) {
      const err = await invoiceRes.json().catch(()=>({}));
      alert(err.detail || 'Не удалось сохранить накладную');
      return false;
    }
    let reviewTasksCreated = 0;
    try {
      reviewTasksCreated = await createInvoiceControlReviewTasksForInvoice(savedInv);
    } catch (err) {
      console.warn('invoice material review tasks failed', err);
    }
    notify('Накладная №'+invoiceNumber+' принята'+(reviewTasksCreated ? ' · задач ИИ-контроля: '+reviewTasksCreated : ''),'invoice');
    addActivity('Принята накладная №'+invoiceNumber);
    await refreshData();
    setNewInvoice(createWarehouseInvoiceForm());
    setShowForm(false);
    alert('Накладная принята!'+(reviewTasksCreated ? '\nСоздано задач ИИ-контроля: '+reviewTasksCreated : ''));
    return true;
  };

  const applyWarehouseMovement = async (recoveredDraft = null) => {
    const scope = movementScope;
    if (!scope || !isMovementScopeCurrent() || activeMovementScopes.has(scope.key)) return {success: false};
    activeMovementScopes.add(scope.key);
    try {
      // Reconcile before preparing/retrying. No new command is allowed to hide
      // an unresolved server-owned draft after reload or a lost response.
      const recovery = await movementRequest(API, `/warehouse-movement-drafts?expectedActorUserId=${scope.actorUserId}`, scope);
      if (!isMovementScopeCurrent()) return {success: false};
      if (!matchesMovementScope(recovery, scope) || !Array.isArray(recovery.drafts)
        || recovery.drafts.some(draft => !matchesMovementScope(draft, scope))) throw new Error('Не удалось подтвердить компанию перемещения');
      const pending = recovery.drafts.find(draft => !draft.complete);
      let intent;
      if (recoveredDraft) {
        if (!matchesMovementScope(recoveredDraft, scope) || recoveredDraft.restricted) throw new Error('Нет доступа к данным перемещения');
        if (pending && pending.draftId !== recoveredDraft.draftId) throw new Error('Сначала завершите сохранённое перемещение');
        intent = {draftId: recoveredDraft.draftId, commands: recoveredDraft.commands.map(row => row.command)};
      } else {
        if (pending) throw new Error('Есть сохранённое перемещение. Используйте «Продолжить перемещение» или отмените неисполненные позиции.');
        if (!newMovement.toLocation) throw new Error('Выберите куда переместить');
        const selected = newMovement.selectedMaterials || [];
        if (!selected.length) throw new Error('Выберите материалы');
        if (selected.some(item => !Number.isFinite(Number(item.quantity)) || Number(item.quantity) <= 0)) throw new Error('Укажите положительное количество для каждого выбранного материала');
        intent = prepareMovementDraft(newMovement, user);
      }
      const prepared = await movementRequest(API, '/warehouse-movement-drafts', scope, {...intent, expectedActorUserId: scope.actorUserId});
      if (!isMovementScopeCurrent()) return {success: false};
      if (!matchesMovementScope(prepared, scope) || prepared.draftId !== intent.draftId
        || prepared.restricted || !Array.isArray(prepared.commands)) throw new Error('Не удалось подтвердить сохранённое перемещение');
      const createdMovements = [];
      for (const row of prepared.commands) {
        if (!isMovementScopeCurrent()) return {success: false};
        if (row.status === 'cancelled') throw new Error('Неисполненные позиции этого перемещения отменены');
        if (row.status === 'committed') { createdMovements.push(row.response); continue; }
        if (row.status !== 'pending') throw new Error('Неизвестный статус перемещения');
        const movement = await movementRequest(API, '/warehouse-movements', scope, {
          ...row.command, draftId: prepared.draftId, expectedActorUserId: scope.actorUserId,
        });
        if (!isMovementScopeCurrent()) return {success: false};
        createdMovements.push(movement);
      }
      if (!isMovementScopeCurrent()) return {success: false};
      setNewMovement(createWarehouseMovementForm());
      try { await refreshData(); } catch (_error) { /* Durable operation remains authoritative. */ }
      // Refresh may await a company/account switch. Never return old snapshots.
      if (!isMovementScopeCurrent()) return {success: false};
      const reviewRequired = createdMovements.filter(row => row?.estimateControl?.needsReview).length;
      notify(reviewRequired ? 'Перемещение выполнено · требуют сметного разбора: ' + reviewRequired : 'Перемещение выполнено', reviewRequired ? 'ai' : 'material');
      return {success: true, moved: createdMovements.length, movements: createdMovements};
    } catch (error) {
      if (isMovementScopeCurrent()) alert((error?.message || 'Ответ сервера не получен') + '. Проверьте результат в блоке восстановления. Сохранённые позиции не нужно вводить заново.');
      return {success: false};
    } finally {
      activeMovementScopes.delete(scope.key);
    }
  };

  const deleteMaterial = async () => {
    alert('Физическое удаление материала объекта отключено. Используйте списание, возврат, перемещение или корректировку, чтобы сохранить историю объекта.');
  };

  const deleteMainMaterial = async () => {
    alert('Физическое удаление материала основного склада отключено. Используйте корректировку склада, перемещение или инвентаризацию, чтобы сохранить историю движения.');
  };

  const saveTool = async () => {
    if (!newTool.name) return false;
    const data = {...newTool, cost: Number(newTool.cost), masterId: newTool.masterId ? Number(newTool.masterId) : null};
    try {
      const response = editingItem
        ? await fetch(API + '/tools/' + editingItem.id, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)})
        : await fetch(API + '/tools', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
      if (!response.ok) {
        const error = await response.json().catch(()=>({}));
        alert(error.detail || 'Не удалось сохранить инструмент');
        return false;
      }
    } catch (_error) {
      alert('Не удалось сохранить инструмент. Проверьте соединение и повторите попытку.');
      return false;
    }
    await refreshData('warehouse');
    setNewTool(createToolForm());
    setEditingItem(null);
    setShowForm(false);
    return true;
  };

  const deleteTool = async (id) => {
    if (window.confirm('Удалить?')) {
      await fetch(API + '/tools/' + id, {method: 'DELETE'});
      await refreshData();
    }
  };

  const issueTool = async (tool) => {
    const {masterName, project, issueType} = issueToolData;
    if (!masterName) {
      alert('Выберите мастера');
      return;
    }
    const updated = {...tool, status: issueType === 'В счёт зарплаты' ? 'У мастера (куплен)' : 'У мастера', location: 'У мастера', masterName, project, issueType};
    await fetch(API + '/tools/' + tool.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(updated)});
    await fetch(API + '/tool-history', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({toolId: tool.id, toolName: tool.name, action: 'Выдача', fromLocation: tool.location, toLocation: 'У мастера — ' + masterName, masterName, project, issueType, condition: 'Исправен', date: new Date().toISOString().split('T')[0], createdBy: user.name})});
    await refreshData();
    setShowIssueToolModal(null);
    setIssueToolData(createIssueToolForm());
  };

  const returnTool = async (tool) => {
    const updated = {...tool, status: returnToolCondition === 'Исправен' ? 'На складе' : 'На ремонте', location: 'Основной склад', masterName: '', project: '', issueType: ''};
    await fetch(API + '/tools/' + tool.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(updated)});
    await fetch(API + '/tool-history', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({toolId: tool.id, toolName: tool.name, action: 'Возврат', fromLocation: 'У мастера — ' + tool.masterName, toLocation: 'Основной склад', masterName: tool.masterName, project: tool.project, condition: returnToolCondition, date: new Date().toISOString().split('T')[0], createdBy: user.name})});
    await refreshData();
    setShowReturnToolModal(null);
    setReturnToolCondition('Исправен');
  };

  return {
    applyWarehouseMovement,
    deleteMaterial,
    deleteMainMaterial,
    openReceiveInvoice,
    saveInvoiceNew,
    saveTool,
    deleteTool,
    issueTool,
    returnTool,
  };
};
