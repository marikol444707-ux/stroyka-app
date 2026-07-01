const authHeaders = (headers = {}) => {
  const token = localStorage.getItem('authToken');
  return token ? {...headers, Authorization: 'Bearer ' + token} : headers;
};

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

export async function fetchProjectLaunchReadiness(API, projectName) {
  const response = await fetch(API + '/project-launch/readiness?project_name=' + encodeURIComponent(projectName), {
    headers: authHeaders(),
  });
  const payload = await readJson(response, 'Не удалось загрузить готовность объекта.');
  return payload.readiness || null;
}

export async function fetchProjectLaunchDrafts(API, projectName) {
  const response = await fetch(API + '/project-launch/drafts?project_name=' + encodeURIComponent(projectName), {
    headers: authHeaders(),
  });
  const payload = await readJson(response, 'Не удалось загрузить черновики запуска.');
  return Array.isArray(payload.items) ? payload.items : [];
}

export async function createProjectLaunchDraft(API, data) {
  const response = await fetch(API + '/project-launch/drafts', {
    method: 'POST',
    headers: authHeaders({'Content-Type': 'application/json'}),
    body: JSON.stringify(data || {}),
  });
  const payload = await readJson(response, 'Не удалось создать черновик запуска.');
  return payload.draft || null;
}

export async function rejectProjectLaunchDraft(API, draftId, reason = '') {
  const response = await fetch(API + '/project-launch/drafts/' + encodeURIComponent(draftId) + '/reject', {
    method: 'POST',
    headers: authHeaders({'Content-Type': 'application/json'}),
    body: JSON.stringify({reason}),
  });
  const payload = await readJson(response, 'Не удалось отклонить черновик запуска.');
  return payload.draft || null;
}
