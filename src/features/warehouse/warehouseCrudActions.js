import { buildScanDraftInvoiceNumber } from '../../utils/accountingInvoices';

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
    const warehouseTarget = location && location !== 'Основной склад' ? 'object' : 'main';
    setNewInvoice({
      number:'',
      date:new Date().toISOString().split('T')[0],
      supplierId:'',
      isNewSupplier:false,
      newSupplierName:'',
      acceptedBy:user?.name||'',
      location,
      project:warehouseTarget === 'object' ? location : '',
      warehouseTarget,
      selectedAction:'receive_to_warehouse',
      sourceType:warehouseTarget === 'object' ? 'manual_project_invoice' : 'manual_main_invoice',
      sourceId:null,
      vat:'Без НДС',
      photos:[],
      photoUrls:[],
      pagesCount:1,
      items:[{name:'',quantity:'',unit:'шт',price:'',category:'',workPackage:''}],
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
    const invoiceNumber = String(newInvoice.number || '').trim() || (isScannedInvoice ? buildScanDraftInvoiceNumber() : '');
    if (!invoiceNumber || newInvoice.items.filter(i=>i.name&&i.quantity).length===0) { alert('Заполните номер накладной и материалы'); return false; }
    if (!newInvoice.location) { alert('Выберите куда оприходовать (основной склад или объект)'); return false; }
    let supplierId = newInvoice.supplierId;
    let resolvedSupplierName = suppliers.find(s=>s.id===Number(supplierId))?.name || '';
    if (newInvoice.isNewSupplier && newInvoice.newSupplierName) {
      const normalizeSupplierName = value => String(value||'')
        .toLowerCase()
        .replace(/ё/g,'е')
        .replace(/(?:,|\s)\s*(инн|кпп|огрн|огрнип|тел\.?|телефон|р\/с|расч[её]тн|адрес)\b.*$/g,' ')
        .replace(/\b(инн|кпп|огрн|огрнип)\s*[:№#-]?\s*\d+\b/g,' ')
        .replace(/\b(ооо|оао|ао|пао|зао|ип|индивидуальный предприниматель)\b/g,' ')
        .replace(/[.,;:()«»"'`/\\]+/g,' ')
        .replace(/\s+/g,' ')
        .trim();
      const existingSupplier = suppliers.find(s=>normalizeSupplierName(s.name)===normalizeSupplierName(newInvoice.newSupplierName));
      if (existingSupplier) {
        supplierId = existingSupplier.id;
        resolvedSupplierName = existingSupplier.name;
      } else {
        const res = await fetch(API+'/suppliers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:newInvoice.newSupplierName,phone:'',email:'',specialization:'',category:'Прочее',rating:5.0,status:'Активный'})});
        if (!res.ok) {
          const err = await res.json().catch(()=>({}));
          alert(err.detail || 'Не удалось сохранить поставщика');
          return false;
        }
        const newSup = await res.json();
        supplierId = newSup.id;
        resolvedSupplierName = newSup.name || newInvoice.newSupplierName;
      }
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
    const selectedAction = newInvoice.selectedAction || 'receive_to_warehouse';
    const sourceType = newInvoice.sourceType || (invoiceProject ? 'manual_project_invoice' : 'manual_main_invoice');
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
      supplierId:Number(supplierId)||0,
      supplierName:resolvedSupplierName||suppliers.find(s=>s.id===Number(supplierId))?.name||newInvoice.newSupplierName||'',
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
      selectedAction,
      sourceType,
      sourceId:newInvoice.sourceId||null,
      materialMatch
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
    setNewInvoice({number:'',date:'',supplierId:'',isNewSupplier:false,newSupplierName:'',acceptedBy:'',location:'Основной склад',project:'',warehouseTarget:'main',selectedAction:'receive_to_warehouse',sourceType:'manual_main_invoice',sourceId:null,vat:'Без НДС',photos:[],photoUrls:[],pagesCount:1,items:[{name:'',quantity:'',unit:'шт',price:'',category:'',workPackage:''}]});
    setShowForm(false);
    alert('Накладная принята!'+(reviewTasksCreated ? '\nСоздано задач ИИ-контроля: '+reviewTasksCreated : ''));
    return true;
  };

  const applyWarehouseMovement = async () => {
    if (!newMovement.toLocation) { alert('Выберите куда переместить'); return; }
    const selected = newMovement.selectedMaterials||[];
    if (selected.length===0) { alert('Выберите материалы'); return; }
    for (const item of selected) {
      if (!item.quantity||Number(item.quantity)<=0) continue;
      const itemWorkPackage = item.workPackage || item.work_package || newMovement.workPackage || '';
      const res = await fetch(API+'/warehouse-movements',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({materialName:item.name,fromLocation:newMovement.fromLocation,toLocation:newMovement.toLocation,quantity:Number(item.quantity),unit:item.unit,workPackage:itemWorkPackage,date:new Date().toISOString().split('T')[0],createdBy:user.name,notes:newMovement.notes})});
      if (!res.ok) {
        const err = await res.json().catch(()=>({}));
        alert(err.detail || 'Не удалось выполнить перемещение материала');
        return;
      }
    }
    notify('Перемещение выполнено','material');
    await refreshData();
    setNewMovement({materialName:'',fromLocation:'Основной склад',toLocation:'',quantity:'',unit:'шт',notes:'',selectedMaterials:[]});
  };

  const deleteMaterial = async (id) => {
    if (!window.confirm('Удалить материал со склада? Это действие доступно только директору.')) return;
    const res = await fetch(API + '/materials/' + id, {method: 'DELETE'});
    if (!res.ok) {
      let msg = 'Не удалось удалить материал';
      try {
        const body = await res.json();
        msg = body.detail || msg;
      } catch {}
      alert(msg);
      return;
    }
    await refreshData();
  };

  const deleteMainMaterial = async (id) => {
    if (!window.confirm('Удалить материал с основного склада? Это действие доступно только директору.')) return;
    const res = await fetch(API + '/warehouse-main/' + id, {method: 'DELETE'});
    if (!res.ok) {
      let msg = 'Не удалось удалить материал';
      try {
        const body = await res.json();
        msg = body.detail || msg;
      } catch {}
      alert(msg);
      return;
    }
    await refreshData();
  };

  const saveTool = async () => {
    if (!newTool.name) return;
    const data = {...newTool, cost: Number(newTool.cost), masterId: newTool.masterId ? Number(newTool.masterId) : null};
    if (editingItem) await fetch(API + '/tools/' + editingItem.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    else await fetch(API + '/tools', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    await refreshData();
    setNewTool({name: '', inventoryNumber: '', cost: '', status: 'На складе', location: 'Основной склад', project: '', masterId: '', masterName: '', issueType: '', notes: ''});
    setEditingItem(null);
    setShowForm(false);
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
    setIssueToolData({masterName: '', project: '', issueType: 'Временно'});
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
