export const createWarehouseCrudActions = ({
  API,
  editingItem,
  issueToolData,
  newTool,
  refreshData,
  returnToolCondition,
  setEditingItem,
  setIssueToolData,
  setNewTool,
  setReturnToolCondition,
  setShowForm,
  setShowIssueToolModal,
  setShowReturnToolModal,
  user,
}) => {
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
    deleteMaterial,
    deleteMainMaterial,
    saveTool,
    deleteTool,
    issueTool,
    returnTool,
  };
};
