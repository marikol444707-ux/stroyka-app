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
