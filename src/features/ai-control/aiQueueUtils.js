export const upsertAiTaskByMarker = async ({
  API,
  marker,
  projectName,
  existingTask,
  queuedRef,
  patch,
  setAiTasks,
  patchAiTaskSilent,
  fetchFn = fetch,
}) => {
  if (!marker || !projectName || !patch) return null;

  if (existingTask) {
    await patchAiTaskSilent(existingTask.id, patch);
    return null;
  }

  if (queuedRef?.current?.has(marker)) return null;
  queuedRef?.current?.add(marker);

  try {
    const res = await fetchFn(API + '/ai-tasks', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        projectName,
        ...patch,
        status: 'Новое',
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      queuedRef?.current?.delete(marker);
      return null;
    }
    setAiTasks(prev => {
      const list = prev || [];
      if (data?.id && list.some(t => Number(t.id) === Number(data.id))) {
        return list.map(t => Number(t.id) === Number(data.id) ? data : t);
      }
      return [data, ...list];
    });
    return data;
  } catch (e) {
    queuedRef?.current?.delete(marker);
    return null;
  }
};

export const queueAiControlDescriptor = async ({
  API,
  descriptor,
  aiTaskByMarker,
  queuedRef,
  setAiTasks,
  patchAiTaskSilent,
}) => {
  if (!descriptor?.marker || !descriptor.projectName) return null;

  const existingTask = aiTaskByMarker(descriptor.marker);
  return upsertAiTaskByMarker({
    API,
    marker: descriptor.marker,
    projectName: descriptor.projectName,
    existingTask,
    queuedRef,
    setAiTasks,
    patchAiTaskSilent,
    patch: {
      title: descriptor.title,
      description: descriptor.description,
      assignedRole: descriptor.assignedRole,
      actionLabel: descriptor.actionLabel,
      actionPayload: JSON.stringify(descriptor.actionPayload),
    },
  });
};

export const closeStaleAiTasksByMarkerPrefix = ({
  tasks,
  projectName,
  markerPrefix,
  activeMarkers,
  parsePayload,
  isOpenStatus,
  patchTaskSilent,
}) => {
  (tasks || [])
    .filter(task => {
      if (!isOpenStatus(task.status)) return false;
      const payload = parsePayload(task);
      return String(payload.marker || '').startsWith(markerPrefix)
        && (payload.projectName || task.projectName || '') === projectName;
    })
    .forEach(task => {
      const payload = parsePayload(task);
      if (payload.marker && !activeMarkers.has(payload.marker)) {
        patchTaskSilent(task.id, {status: 'Закрыто'});
      }
    });
};
