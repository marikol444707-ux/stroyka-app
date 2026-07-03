import { createMeasurementDocForm } from './projectMeasurementInitialForms';

const alertMessage = (message) => {
  if (typeof window !== 'undefined' && typeof window.alert === 'function') {
    window.alert(message);
  }
};

const confirmMessage = (message) => (
  typeof window !== 'undefined' && typeof window.confirm === 'function'
    ? window.confirm(message)
    : false
);

export function createProjectMeasurementActions({
  API,
  C,
  newMeasurementDoc,
  project,
  refreshData,
  setMeasurementDraftLoadingId,
  setNewMeasurementDoc,
  setShowMeasurementForm,
  user,
}) {
  const statusMeta = (st) => st === 'Принято'
    ? [C.success, C.successLight, C.successBorder]
    : st === 'На проверке'
      ? [C.warning, C.warningLight, C.warningBorder]
      : st === 'Отклонено'
        ? [C.danger, C.dangerLight, C.dangerBorder]
        : [C.textSec, C.bgGray, C.border];

  const saveMeasurement = async () => {
    if (!newMeasurementDoc.title.trim() && !newMeasurementDoc.fileUrl && !newMeasurementDoc.photoUrl) {
      alertMessage('Укажите название или загрузите файл/фото');
      return;
    }
    await fetch(API + '/project-measurements', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        ...newMeasurementDoc,
        projectName: project.name,
        roomsCreated: Number(newMeasurementDoc.roomsCreated || 0),
        uploadedBy: user.name,
      }),
    });
    setNewMeasurementDoc(createMeasurementDocForm());
    setShowMeasurementForm(false);
    await refreshData();
  };

  const updateMeasurement = async (doc, patch) => {
    await fetch(API + '/project-measurements/' + doc.id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(patch),
    });
    await refreshData();
  };

  const deleteMeasurement = async (doc) => {
    if (!confirmMessage('Удалить исходник «' + (doc.title || doc.docType || 'обмер') + '»?')) return;
    await fetch(API + '/project-measurements/' + doc.id, {method: 'DELETE'});
    await refreshData();
  };

  const generateRoomDrafts = async (doc) => {
    setMeasurementDraftLoadingId(doc.id);
    try {
      const r = await fetch(API + '/project-measurements/' + doc.id + '/ai-draft-rooms', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({replaceExisting: true}),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || data.detail) alertMessage('Не удалось разобрать источник: ' + (data.detail || 'ошибка'));
      else if (!data.created) alertMessage('ИИ не нашёл помещений. Добавьте текст в комментарий или загрузите более читаемый скан.');
    } finally {
      setMeasurementDraftLoadingId(null);
      await refreshData();
    }
  };

  const acceptRoomDraft = async (draft) => {
    await fetch(API + '/measurement-room-drafts/' + draft.id + '/accept', {method: 'POST'});
    await refreshData();
  };

  const rejectRoomDraft = async (draft) => {
    await fetch(API + '/measurement-room-drafts/' + draft.id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status: 'Отклонено'}),
    });
    await refreshData();
  };

  return {
    acceptRoomDraft,
    deleteMeasurement,
    generateRoomDrafts,
    rejectRoomDraft,
    saveMeasurement,
    statusMeta,
    updateMeasurement,
  };
}
