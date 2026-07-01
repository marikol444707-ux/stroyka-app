import { buildLeadPayload } from './leadUtils';

export const createCrmActions = ({
  API,
  notify,
  setLeads,
  setProjects,
  user,
}) => {
  const reloadLeads = async () => {
    const rows = await fetch(API + '/crm/lead-summaries').then(r => r.json()).catch(() => []);
    setLeads(Array.isArray(rows) ? rows : []);
    return rows;
  };

  const saveLead = async (lead) => {
    const body = buildLeadPayload(lead);
    if (lead.id) {
      await fetch(API + '/crm/leads/' + lead.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    } else {
      await fetch(API + '/crm/leads', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(buildLeadPayload(lead, {
        createdBy: user.name,
        createdAt: new Date().toISOString().split('T')[0],
        includeCreateMeta: true,
      }))});
    }
    await reloadLeads();
  };

  const deleteLead = async (id) => {
    await fetch(API + '/crm/leads/' + id, {method: 'DELETE'});
    await reloadLeads();
  };

  const createProjectFromLead = async (lead) => {
    if (!lead?.id) return;
    if (lead.projectId) {
      notify('По этой заявке объект уже создан', 'project');
      return;
    }
    const projectName = window.prompt('Название объекта:', lead.name || ('Заявка #' + lead.id));
    if (projectName === null) return;
    const cleanName = String(projectName || '').trim();
    if (!cleanName) return alert('Укажите название объекта');
    const res = await fetch(API + '/crm/leads/' + lead.id + '/create-project', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({projectName: cleanName, budget: Number(lead.budget) || 0}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return alert(data.detail || 'Не удалось создать объект из заявки');
    const [ls, ps] = await Promise.all([
      fetch(API + '/crm/lead-summaries').then(r => r.json()).catch(() => []),
      fetch(API + '/projects').then(r => r.json()).catch(() => []),
    ]);
    setLeads(Array.isArray(ls) ? ls : []);
    setProjects(Array.isArray(ps) ? ps : []);
    notify((data.alreadyExists ? 'Объект уже был создан: ' : 'Создан объект: ') + (data.project?.name || cleanName), 'project');
  };

  return {
    saveLead,
    deleteLead,
    createProjectFromLead,
  };
};
