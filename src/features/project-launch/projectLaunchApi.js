const authHeaders = (project, headers = {}) => {
  const companyId = Number(project?.companyId ?? project?.company_id);
  if (!Number.isSafeInteger(companyId) || companyId <= 0 || !Number.isSafeInteger(Number(project?.id)) || Number(project.id) <= 0) {
    throw new Error('Компания или объект не определены. Обновите страницу.');
  }
  return { ...headers, 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company' };
};
const projectQuery = project => 'project_name=' + encodeURIComponent(project.name || '') + '&project_id=' + encodeURIComponent(project.id);

const readJson = async (response, fallbackMessage) => {
  let payload = null;
  try {
    payload = await response.json();
  } catch (_) {}
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.error || fallbackMessage);
  }
  return payload;
};

export async function fetchProjectLaunchReadiness(API, project) {
  const response = await fetch(API + '/project-launch/readiness?' + projectQuery(project), {
    headers: authHeaders(project),
  });
  const payload = await readJson(response, 'Не удалось загрузить готовность объекта.');
  return payload.readiness || null;
}

export async function fetchProjectLaunchDrafts(API, project) {
  const response = await fetch(API + '/project-launch/drafts?' + projectQuery(project), {
    headers: authHeaders(project),
  });
  const payload = await readJson(response, 'Не удалось загрузить черновики запуска.');
  return Array.isArray(payload.items) ? payload.items : [];
}

export async function createProjectLaunchDraft(API, data, project) {
  const response = await fetch(API + '/project-launch/drafts', {
    method: 'POST',
    headers: authHeaders(project, {'Content-Type': 'application/json'}),
    body: JSON.stringify({ ...data, projectId: project.id, projectName: project.name }),
  });
  const payload = await readJson(response, 'Не удалось создать черновик запуска.');
  return payload.draft || null;
}

export async function rejectProjectLaunchDraft(API, draftId, reason, project) {
  const response = await fetch(API + '/project-launch/drafts/' + encodeURIComponent(draftId) + '/reject', {
    method: 'POST',
    headers: authHeaders(project, {'Content-Type': 'application/json'}),
    body: JSON.stringify({reason}),
  });
  const payload = await readJson(response, 'Не удалось отклонить черновик запуска.');
  return payload.draft || null;
}
