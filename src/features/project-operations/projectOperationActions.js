import {
  createChecklistForm,
  createDoorForm,
  createPrescriptionForm,
  createProjectStageForm,
  createRoomForm,
  createWeatherForm,
  createWindowForm,
} from './projectOperationInitialForms';
import { createWarehouseForm } from '../warehouse/warehouseInitialForms';

export function createProjectOperationActions({
  API,
  CHECKLIST_TEMPLATES,
  EMPTY_ESTIMATE_CHANGE,
  companyReqForm,
  customRoomTypes,
  draftRoomDoors,
  draftRoomWindows,
  editingItem,
  loadChecklistItems,
  newChecklist,
  newDoor,
  newPrescription,
  newRoom,
  newStage,
  newUnexpected,
  newWarehouse,
  newWeather,
  newWindow,
  notify,
  refreshData,
  roomDoors,
  roomWindows,
  setCustomRoomTypes,
  setDraftRoomDoors,
  setDraftRoomWindows,
  setEditingDoor,
  setEditingItem,
  setEditingWindow,
  setExpandedRoom,
  setNewChecklist,
  setNewDoor,
  setNewPrescription,
  setNewRoom,
  setNewStage,
  setNewUnexpected,
  setNewWarehouse,
  setNewWeather,
  setNewWindow,
  setRoomDoors,
  setRoomWindows,
  setShowForm,
  setShowRoomForm,
  setTbJournal,
  setWeatherLog,
  tbJournal,
  toNum,
  user,
  weatherLog,
}) {
  const checkedFetch = async (...args) => {
    const response = await fetch(...args);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === 'string' ? body.detail : 'Не удалось сохранить изменения');
    }
    return response;
  };
  const guarded = action => async (...args) => {
    try { return await action(...args); }
    catch (error) { notify(error.message || 'Ошибка сети. Изменения не подтверждены.', 'error'); return false; }
  };

  const saveRoom = async () => {
    if (!newRoom.name || !newRoom.project) return;
    const baseRoomTypes = ['Комната', 'Кабинет', 'Коридор', 'Санузел', 'Кухня', 'Балкон', 'Лестница', 'Холл', 'Техническое'];
    const roomType = newRoom.roomType && newRoom.roomType !== 'Другое' ? newRoom.roomType : 'Комната';
    const data = {
      project: newRoom.project,
      projectId: newRoom.projectId || null,
      name: newRoom.name,
      floor: Number(newRoom.floor) || 1,
      liter: newRoom.liter || '',
      roomType,
      floorArea: Number(newRoom.floorArea) || 0,
      wallArea: Number(newRoom.wallArea) || 0,
      ceilingArea: Number(newRoom.ceilingArea) || 0,
      height: Number(newRoom.height) || 0,
      ceilingType: newRoom.ceilingType,
      wallMaterial: newRoom.wallMaterial,
      floorMaterial: newRoom.floorMaterial,
      windows: 0,
      doors: 0,
      photoUrl: newRoom.photoUrl || '',
      notes: newRoom.notes,
    };
    let createdRoomId = null;
    if (editingItem) {
      await checkedFetch(API + '/rooms/' + editingItem.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
      createdRoomId = editingItem.id;
    } else {
      if (roomType && !baseRoomTypes.includes(roomType)) {
        const updated = [...new Set([...customRoomTypes, roomType])];
        setCustomRoomTypes(updated);
        localStorage.setItem('customRoomTypes', JSON.stringify(updated));
      }
      const res = await checkedFetch(API + '/rooms', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
      const created = await res.json().catch(() => ({}));
      createdRoomId = created?.id || null;
      if (!createdRoomId) throw new Error('Сервер не подтвердил сохранение помещения');
      // Keep the confirmed parent identity if a subsequent child save fails.
      setEditingItem({ ...data, id: createdRoomId });
    }
    // Persist children one at a time and retain only unconfirmed drafts for retry.
    const windowRows = draftRoomWindows.filter(w => Number(w.width || 0) > 0 && Number(w.height || 0) > 0);
    const doorRows = draftRoomDoors.filter(d => Number(d.width || 0) > 0 && Number(d.height || 0) > 0);
    for (let i = 0; i < windowRows.length; i++) {
      await checkedFetch(API + '/room-windows', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...windowRows[i], roomId: Number(createdRoomId) }) });
      setDraftRoomWindows(windowRows.slice(i + 1));
    }
    for (let i = 0; i < doorRows.length; i++) {
      await checkedFetch(API + '/room-doors', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...doorRows[i], roomId: Number(createdRoomId) }) });
      setDraftRoomDoors(doorRows.slice(i + 1));
    }
    await refreshData();
    setNewRoom(createRoomForm());
    setDraftRoomWindows([]);
    setDraftRoomDoors([]);
    setEditingItem(null);
    setExpandedRoom(createdRoomId);
    setShowRoomForm(false);
  };

  const deleteRoom = async (id) => {
    if (window.confirm('Удалить?')) {
      await checkedFetch(API + '/rooms/' + id, { method: 'DELETE' });
      await refreshData();
    }
  };

  const saveWindow = async roomId => {
    if (!newWindow.width || !newWindow.height) return;
    const response = await checkedFetch(API + '/room-windows', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...newWindow, roomId: Number(roomId) }) });
    const saved = await response.json();
    const id = Array.isArray(saved) ? saved[0] : saved.id;
    if (!id) throw new Error('Сервер не подтвердил сохранение окна');
    setRoomWindows(prev => [...prev, { ...newWindow, id, room_id: Number(roomId), window_type: newWindow.windowType, reveal_depth: newWindow.revealDepth, reveal_material: newWindow.revealMaterial, order_num: newWindow.orderNum }]);
    setNewWindow(createWindowForm({ name: 'Окно ' + (roomWindows.filter(w => w.room_id === roomId).length + 2) }));
  };
  const updateWindow = async win => {
    await checkedFetch(API + '/room-windows/' + win.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(win) });
    setRoomWindows(prev => prev.map(row => row.id === win.id ? { ...row, ...win } : row));
    setEditingWindow(null);
  };
  const deleteWindow = async id => {
    await checkedFetch(API + '/room-windows/' + id, { method: 'DELETE' });
    setRoomWindows(prev => prev.filter(row => row.id !== id));
  };
  const saveDoor = async roomId => {
    if (!newDoor.width || !newDoor.height) return;
    const response = await checkedFetch(API + '/room-doors', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...newDoor, roomId: Number(roomId) }) });
    const saved = await response.json();
    const id = Array.isArray(saved) ? saved[0] : saved.id;
    if (!id) throw new Error('Сервер не подтвердил сохранение двери');
    setRoomDoors(prev => [...prev, { ...newDoor, id, room_id: Number(roomId), door_type: newDoor.doorType, door_purpose: newDoor.doorPurpose, reveal_depth: newDoor.revealDepth, reveal_material: newDoor.revealMaterial, order_num: newDoor.orderNum }]);
    setNewDoor(createDoorForm({ name: 'Дверь ' + (roomDoors.filter(d => d.room_id === roomId).length + 2) }));
  };
  const updateDoor = async door => {
    await checkedFetch(API + '/room-doors/' + door.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(door) });
    setRoomDoors(prev => prev.map(row => row.id === door.id ? { ...row, ...door } : row));
    setEditingDoor(null);
  };
  const deleteDoor = async id => {
    await checkedFetch(API + '/room-doors/' + id, { method: 'DELETE' });
    setRoomDoors(prev => prev.filter(row => row.id !== id));
  };

  const saveWeather = () => {
    if (!newWeather.projectName || !newWeather.date) return;
    const entry = { ...newWeather, id: Date.now(), createdBy: user.name, temperature: Number(newWeather.temperature || 0), windSpeed: Number(newWeather.windSpeed || 0) };
    const updated = [...weatherLog, entry];
    setWeatherLog(updated);
    localStorage.setItem('weatherLog', JSON.stringify(updated));
    setNewWeather(createWeatherForm());
  };

  const saveTbEntry = async (data) => {
    const payload = {
      projectName: data.project || data.projectName || '',
      masterName: data.masterName || '',
      instructor: data.instructor || (user ? user.name : ''),
      instructionType: data.type || data.instructionType || 'Первичный инструктаж на рабочем месте',
      program: data.program || '',
      instructionText: data.instructionText || '',
      participants: data.participants || [],
      photoUrl: data.photoUrl || '',
      date: data.date || new Date().toISOString().split('T')[0],
    };
    const response = await checkedFetch(API + '/tb-journal', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const saved = await response.json();
    if (!saved?.id) throw new Error('Сервер не подтвердил запись инструктажа');
    const localEntry = { ...payload, id: saved.id, createdBy: user.name, project: payload.projectName, type: payload.instructionType };
    const updated = [...tbJournal, localEntry];
    setTbJournal(updated);
    localStorage.setItem('tbJournal', JSON.stringify(updated));
  };

  const saveWarehouse = async () => {
    if (!newWarehouse.name) return;
    if (editingItem) await checkedFetch(API + '/warehouses/' + editingItem.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newWarehouse) });
    else await checkedFetch(API + '/warehouses', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newWarehouse) });
    await refreshData();
    setNewWarehouse(createWarehouseForm());
    setEditingItem(null);
    setShowForm(false);
  };

  const deleteWarehouse = async (id) => {
    if (window.confirm('Удалить склад?')) {
      await checkedFetch(API + '/warehouses/' + id, { method: 'DELETE' });
      await refreshData();
    }
  };

  const saveCompanyRequisites = async () => {
    const response = await fetch(API + '/company-requisites', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(companyReqForm) });
    if (!response.ok) {
      alert('Не удалось сохранить реквизиты');
      return null;
    }
    const saved = await response.json();
    await refreshData();
    alert('Реквизиты сохранены!');
    const {ok: _ok, ...profile} = saved;
    return profile;
  };

  const saveProjectStage = async (projectId, projectName) => {
    if (!newStage.name) return;
    await checkedFetch(API + '/project-stages', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...newStage, projectId, projectName, progress: Number(newStage.progress) || 0 }) });
    await refreshData();
    setNewStage(createProjectStageForm());
  };

  const updateStage = async (stage) => {
    await checkedFetch(API + '/project-stages/' + stage.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(stage) });
    await refreshData();
  };

  const deleteStage = async (id) => {
    if (window.confirm('Удалить?')) {
      await checkedFetch(API + '/project-stages/' + id, { method: 'DELETE' });
      await refreshData();
    }
  };

  const saveChecklist = async (projectId, projectName) => {
    if (!newChecklist.name) return;
    const res = await checkedFetch(API + '/project-checklists', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...newChecklist, projectId, projectName, createdBy: user.name, createdAt: new Date().toISOString().split('T')[0] }) });
    const cl = await res.json();
    if (newChecklist.template && CHECKLIST_TEMPLATES[newChecklist.template]) {
      const items = CHECKLIST_TEMPLATES[newChecklist.template];
      for (let i = 0; i < items.length; i++) {
        await checkedFetch(API + '/checklist-items', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ checklistId: cl.id, name: items[i], checked: false, orderNum: i }) });
      }
    }
    await refreshData();
    setNewChecklist(createChecklistForm());
  };

  const toggleChecklistItem = async (item) => {
    await checkedFetch(API + '/checklist-items/' + item.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ checked: !item.checked, checkedBy: !item.checked ? user.name : '', checkedAt: !item.checked ? new Date().toISOString().split('T')[0] : '' }) });
    await loadChecklistItems(item.checklistId);
  };

  const savePrescription = async (projectName) => {
    if (!newPrescription.violation) return;
    await checkedFetch(API + '/prescriptions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...newPrescription, projectName, issuedBy: user.name, issuedByRole: user.role }) });
    await refreshData();
    setNewPrescription(createPrescriptionForm());
  };

  const saveUnexpectedWork = async (projectName) => {
    if (!newUnexpected.description) return;
    const baseQty = toNum(newUnexpected.baseQuantity);
    const newQty = toNum(newUnexpected.newRequiredQuantity);
    const deltaQty = newUnexpected.changeType === 'Дополнительный объём к строке сметы'
      ? Math.max(0, newQty - baseQty)
      : toNum(newUnexpected.quantity);
    const price = toNum(newUnexpected.price);
    await checkedFetch(API + '/unexpected-works', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
      ...newUnexpected,
      projectName,
      quantity: deltaQty,
      deltaQuantity: deltaQty,
      baseQuantity: baseQty,
      newRequiredQuantity: newQty,
      price,
      total: deltaQty * price,
      addedBy: user.name,
      addedByRole: user.role
    }) });
    notify('Новое изменение к смете: ' + newUnexpected.description, 'unexpected');
    await refreshData();
    setNewUnexpected(EMPTY_ESTIMATE_CHANGE);
  };

  const approveUnexpectedWork = async (work, price) => {
    const qty = Number(work.deltaQuantity || work.quantity || 0);
    const total = qty * Number(price);
    const status = work.changeType === 'Исключение объёма' ? 'Утверждено' : 'Утверждено отдельной допработой';
    await checkedFetch(API + '/unexpected-works/' + work.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status, price: Number(price), total, approvedBy: user.name, approvedAt: new Date().toISOString().split('T')[0] }) });
    await refreshData();
  };

  return {
    approveUnexpectedWork: guarded(approveUnexpectedWork),
    deleteDoor: guarded(deleteDoor),
    deleteRoom: guarded(deleteRoom),
    deleteStage: guarded(deleteStage),
    deleteWarehouse: guarded(deleteWarehouse),
    deleteWindow: guarded(deleteWindow),
    saveChecklist: guarded(saveChecklist),
    saveCompanyRequisites,
    saveDoor: guarded(saveDoor),
    savePrescription: guarded(savePrescription),
    saveProjectStage: guarded(saveProjectStage),
    saveRoom: guarded(saveRoom),
    saveTbEntry: guarded(saveTbEntry),
    saveUnexpectedWork: guarded(saveUnexpectedWork),
    saveWarehouse: guarded(saveWarehouse),
    saveWeather: guarded(saveWeather),
    saveWindow: guarded(saveWindow),
    toggleChecklistItem: guarded(toggleChecklistItem),
    updateDoor: guarded(updateDoor),
    updateStage: guarded(updateStage),
    updateWindow: guarded(updateWindow),
  };
}
