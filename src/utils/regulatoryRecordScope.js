import { qualityJournalOwnerId } from './projectObjectLinksUtils';

export const selectRegulatoryRecords = (rows, project) => {
  const companyId = qualityJournalOwnerId(project, 'companyId', 'company_id');
  const projectId = qualityJournalOwnerId(project, 'id');
  if (companyId === null || projectId === null) return [];
  return (rows || []).filter(row => qualityJournalOwnerId(row, 'companyId', 'company_id') === companyId
    && qualityJournalOwnerId(row, 'projectId', 'project_id') === projectId);
};

// Callers clear drafts or refresh lists only after a confirmed successful write.
export const saveRegulatoryRecord = async (url, options) => {
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === 'string' ? body.detail : `Ошибка ${response.status}`);
    }
    return true;
  } catch (error) {
    window.alert('Изменение не подтверждено: ' + error.message + '. Введённые данные сохранены в форме.');
    return false;
  }
};
