import {
  projectSitePublicationDraft,
  projectSitePublicationPayload,
} from '../../utils/projectSitePublicationUtils';

export const createProjectCrudActions = ({
  API,
  brigadeContracts,
  editingItem,
  newClient,
  newProject,
  newTask,
  notify,
  projects,
  readApiResult,
  refreshData,
  setEditingItem,
  setNewClient,
  setNewProject,
  setNewTask,
  setShowForm,
  setSitePublicationDrafts,
  sitePublicationDrafts,
  addActivity,
}) => {
  const saveProject = async () => {
    if (!newProject.name) {
      alert('Введите название');
      return;
    }
    const data = {...newProject, budget: Number(newProject.budget)};
    ['archived', 'archivedAt', 'archived_at', 'id'].forEach(key => delete data[key]);
    try {
      if (editingItem) {
        await readApiResult(await fetch(API + '/projects/' + editingItem.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)}));
      } else {
        await readApiResult(await fetch(API + '/projects', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)}));
        notify('Создан проект: ' + newProject.name, 'project');
      }
      await refreshData();
      addActivity((editingItem ? 'Обновил' : 'Создал') + ' проект: ' + newProject.name);
      if (!editingItem && newProject.clientEmail && newProject.clientPassword) {
        await readApiResult(await fetch(API + '/users', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: newProject.client || newProject.name, email: newProject.clientEmail, password: newProject.clientPassword, role: 'заказчик', projectName: newProject.name})}));
        alert('Заказчик создан! Логин: ' + newProject.clientEmail + ' Пароль: ' + newProject.clientPassword);
      }
      setNewProject({name: '', client: '', status: 'Планирование', budget: '', deadline: '', progress: 0, tasks: [], pricelistId: null});
      setEditingItem(null);
      setShowForm(false);
    } catch (err) {
      alert('Не удалось сохранить проект: ' + (err.message || err));
    }
  };

  const updateProjectProgress = async (projectName) => {
    const contracts = brigadeContracts.filter(bc => bc.projectName === projectName);
    if (!contracts.length) return;
    let totalQty = 0;
    let doneQty = 0;
    for (const bc of contracts) {
      const res = await fetch(API + '/brigade-contract-items/' + bc.id);
      const items = await res.json();
      for (const item of items) {
        totalQty += Number(item.quantity || 0);
        doneQty += Number(item.doneQuantity || 0);
      }
    }
    const pct = totalQty > 0 ? Math.round(doneQty / totalQty * 100) : 0;
    const proj = projects.find(p => p.name === projectName);
    if (proj && proj.progress !== pct) {
      await fetch(API + '/projects/' + proj.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...proj, progress: pct})});
      await refreshData();
    }
  };

  const editProject = (p) => {
    setEditingItem(p);
    setNewProject({...p});
    setShowForm(true);
  };

  const projectSiteDraft = (p) => projectSitePublicationDraft(p, sitePublicationDrafts);

  const updateProjectSiteDraft = (projectId, patch) => {
    setSitePublicationDrafts(prev => ({
      ...prev,
      [projectId]: {
        ...projectSiteDraft(projects.find(pr => pr.id === projectId) || {id: projectId}),
        ...patch,
      },
    }));
  };

  const saveProjectSitePublication = async (p) => {
    const d = projectSiteDraft(p);
    try {
      await readApiResult(await fetch(API + '/projects/' + p.id + '/site-publication', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(projectSitePublicationPayload(p, d)),
      }));
      setSitePublicationDrafts(prev => {
        const next = {...prev};
        delete next[p.id];
        return next;
      });
      await refreshData();
      notify('Публикация объекта обновлена: ' + p.name, 'project');
    } catch (err) {
      alert('Не удалось сохранить публикацию: ' + (err.message || err));
    }
  };

  const addTask = async (p) => {
    if (!newTask) return;
    await fetch(API + '/projects/' + p.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...p, tasks: [...(p.tasks || []), newTask]})});
    await refreshData();
    setNewTask('');
  };

  const removeTask = async (p, i) => {
    await fetch(API + '/projects/' + p.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...p, tasks: p.tasks.filter((_, idx) => idx !== i)})});
    await refreshData();
  };

  const saveClient = async () => {
    if (!newClient.name) return;
    if (editingItem) await fetch(API + '/clients/' + editingItem.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(newClient)});
    else await fetch(API + '/clients', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(newClient)});
    await refreshData();
    setNewClient({name: '', phone: '', email: '', status: 'Активный', notes: ''});
    setEditingItem(null);
    setShowForm(false);
  };

  const deleteClient = async (id) => {
    if (window.confirm('Удалить?')) {
      await fetch(API + '/clients/' + id, {method: 'DELETE'});
      await refreshData();
    }
  };

  return {
    saveProject,
    updateProjectProgress,
    editProject,
    projectSiteDraft,
    updateProjectSiteDraft,
    saveProjectSitePublication,
    addTask,
    removeTask,
    saveClient,
    deleteClient,
  };
};
