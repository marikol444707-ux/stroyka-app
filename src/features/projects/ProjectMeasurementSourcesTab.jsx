import React from 'react';

export default function ProjectMeasurementSourcesTab({ ctx, project }) {
  const {
    API,
    Bot,
    C,
    Check,
    Eye,
    FileText,
    PROJECT_MEASUREMENT_DOC_TYPES,
    PROJECT_MEASUREMENT_SOURCE_TYPES,
    PROJECT_MEASUREMENT_STATUSES,
    PhotoAttachmentField,
    Plus,
    Trash2,
    Upload,
    X,
    appendPhotos,
    badge,
    btnB,
    btnG,
    btnGr,
    btnO,
    btnR,
    card,
    createProjectMeasurementActions,
    fileSrc,
    fmtMeasure,
    inp,
    isMobile,
    measurementDraftLoadingId,
    measurementRoomDrafts,
    newMeasurementDoc,
    projectMeasurements,
    refreshData,
    renderEstimateMeasurementComparisonPanel,
    roomCompleteness,
    rooms,
    setActiveProjectTab,
    setMeasurementDraftLoadingId,
    setNewMeasurementDoc,
    setShowMeasurementForm,
    setShowPhotoModal,
    setUploadingMeasurementDoc,
    showMeasurementForm,
    uploadPhoto,
    uploadingMeasurementDoc,
    user,
  } = ctx;

  const docs = (projectMeasurements || []).filter(d => d.projectName === project.name);
  const drafts = (measurementRoomDrafts || []).filter(d => d.projectName === project.name);
  const projectRooms = rooms.filter(r => r.project === project.name);
  const roomChecks = projectRooms.map(roomCompleteness);
  const fullRooms = roomChecks.filter(x => x.status === 'Обмер полный').length;
  const missingRooms = roomChecks.filter(x => x.status === 'Не хватает данных').length;
  const acceptedDocs = docs.filter(d => d.status === 'Принято').length;
  const reviewDocs = docs.filter(d => d.status === 'На проверке').length;
  const pendingDrafts = drafts.filter(d => d.status === 'Черновик ИИ').length;
  const acceptedDrafts = drafts.filter(d => d.acceptedRoomId || d.status === 'Принято').length;
  const canEditMeasurements = user && ['директор', 'зам_директора', 'прораб', 'главный_инженер', 'сметчик'].includes(user.role);
  const {
    acceptRoomDraft,
    deleteMeasurement,
    generateRoomDrafts,
    rejectRoomDraft,
    saveMeasurement,
    statusMeta,
    updateMeasurement,
  } = createProjectMeasurementActions({
    API,
    C,
    newMeasurementDoc,
    project,
    refreshData,
    setMeasurementDraftLoadingId,
    setNewMeasurementDoc,
    setShowMeasurementForm,
    user,
  });

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginBottom: '14px' }}>
        <div>
          <b style={{ color: C.text, fontSize: '15px' }}>📐 Проект / Обмеры</b>
          <p style={{ color: C.textSec, fontSize: '12px', margin: '4px 0 0' }}>Исходники объёмов: проект, экспликации, ведомости окон/дверей, ручные и фактические обмеры.</p>
        </div>
        {canEditMeasurements && (
          <button onClick={() => setShowMeasurementForm(!showMeasurementForm)} style={btnO}>
            <Plus size={14} />Добавить источник
          </button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr 1fr' : 'repeat(auto-fit,minmax(130px,1fr))', gap: '10px', marginBottom: '14px' }}>
        <div style={{ padding: '12px', borderRadius: '10px', backgroundColor: C.bgWhite, border: '1.5px solid ' + C.border }}>
          <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Исходников</p>
          <b style={{ color: C.text, fontSize: '20px' }}>{docs.length}</b>
        </div>
        <div style={{ padding: '12px', borderRadius: '10px', backgroundColor: acceptedDocs ? C.successLight : C.bgWhite, border: '1.5px solid ' + (acceptedDocs ? C.successBorder : C.border) }}>
          <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Принято</p>
          <b style={{ color: acceptedDocs ? C.success : C.text, fontSize: '20px' }}>{acceptedDocs}</b>
        </div>
        <div style={{ padding: '12px', borderRadius: '10px', backgroundColor: reviewDocs ? C.warningLight : C.bgWhite, border: '1.5px solid ' + (reviewDocs ? C.warningBorder : C.border) }}>
          <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>На проверке</p>
          <b style={{ color: reviewDocs ? C.warning : C.text, fontSize: '20px' }}>{reviewDocs}</b>
        </div>
        <div style={{ padding: '12px', borderRadius: '10px', backgroundColor: pendingDrafts ? C.infoLight : C.bgWhite, border: '1.5px solid ' + (pendingDrafts ? C.infoBorder : C.border) }}>
          <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Черновики ИИ</p>
          <b style={{ color: pendingDrafts ? C.info : C.text, fontSize: '20px' }}>{pendingDrafts}</b>
          <span style={{ color: C.textMuted, fontSize: '11px', marginLeft: '6px' }}>принято {acceptedDrafts}</span>
        </div>
        <div style={{ padding: '12px', borderRadius: '10px', backgroundColor: missingRooms ? C.warningLight : C.successLight, border: '1.5px solid ' + (missingRooms ? C.warningBorder : C.successBorder) }}>
          <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Помещения</p>
          <b style={{ color: missingRooms ? C.warning : C.success, fontSize: '20px' }}>{fullRooms + '/' + projectRooms.length}</b>
        </div>
      </div>

      {showMeasurementForm && canEditMeasurements && (
        <div style={{ ...card, padding: '16px', marginBottom: '14px', backgroundColor: C.bg }}>
          <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr 1fr', gap: '8px' }}>
            <select value={newMeasurementDoc.sourceType} onChange={e => setNewMeasurementDoc({ ...newMeasurementDoc, sourceType: e.target.value })} style={{ ...inp, marginBottom: 0 }}>
              {PROJECT_MEASUREMENT_SOURCE_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
            <select value={newMeasurementDoc.docType} onChange={e => setNewMeasurementDoc({ ...newMeasurementDoc, docType: e.target.value })} style={{ ...inp, marginBottom: 0 }}>
              {PROJECT_MEASUREMENT_DOC_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
            <select value={newMeasurementDoc.status} onChange={e => setNewMeasurementDoc({ ...newMeasurementDoc, status: e.target.value })} style={{ ...inp, marginBottom: 0 }}>
              {PROJECT_MEASUREMENT_STATUSES.map(t => <option key={t}>{t}</option>)}
            </select>
            <input placeholder="Название / лист / файл" value={newMeasurementDoc.title} onChange={e => setNewMeasurementDoc({ ...newMeasurementDoc, title: e.target.value })} style={{ ...inp, marginBottom: 0 }} />
            <input placeholder="Создано помещений" type="number" min="0" inputMode="numeric" value={newMeasurementDoc.roomsCreated} onChange={e => setNewMeasurementDoc({ ...newMeasurementDoc, roomsCreated: e.target.value })} style={{ ...inp, marginBottom: 0 }} />
            <label style={{ ...btnG, cursor: 'pointer', justifyContent: 'center', margin: 0 }}>
              <Upload size={14} />{uploadingMeasurementDoc ? 'Загрузка...' : (newMeasurementDoc.fileUrl ? 'Файл загружен' : 'Загрузить файл')}
              <input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,image/*" style={{ display: 'none' }} onChange={async e => {
                const f = e.target.files[0];
                if (!f) return;
                setUploadingMeasurementDoc(true);
                const url = await uploadPhoto(f, { projectName: project.name, context: 'project-measurements' });
                setUploadingMeasurementDoc(false);
                if (url) setNewMeasurementDoc(prev => ({ ...prev, fileUrl: url, title: prev.title || f.name }));
              }} />
            </label>
          </div>
          <div style={{ marginTop: '8px' }}>
            <PhotoAttachmentField
              C={C}
              btnG={btnG}
              value={newMeasurementDoc.photoUrl || ''}
              onChange={photoUrl => {
                const firstPhoto = String(photoUrl || '').split(',').map(url => url.trim()).filter(Boolean)[0] || '';
                setNewMeasurementDoc(prev => ({ ...prev, photoUrl, fileUrl: prev.fileUrl || firstPhoto, title: prev.title || (firstPhoto ? 'Фото обмера' : '') }));
              }}
              appendPhotos={appendPhotos}
              fileSrc={fileSrc}
              setShowPhotoModal={setShowPhotoModal}
              projectName={project.name}
              context="project-measurements"
              title="Фото/сканы листов замеров"
            />
          </div>
          <textarea placeholder="Комментарий: откуда взяты объёмы, что нужно проверить, какие помещения создать" value={newMeasurementDoc.notes} onChange={e => setNewMeasurementDoc({ ...newMeasurementDoc, notes: e.target.value })} style={{ ...inp, minHeight: '70px', resize: 'vertical', marginTop: '8px' }} />
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button onClick={saveMeasurement} style={btnO}><Check size={14} />Сохранить</button>
            <button onClick={() => setShowMeasurementForm(false)} style={btnG}><X size={14} />Отмена</button>
          </div>
        </div>
      )}

      <div style={{ ...card, padding: '14px', marginBottom: '14px', backgroundColor: missingRooms ? C.warningLight : C.successLight, border: '1.5px solid ' + (missingRooms ? C.warningBorder : C.successBorder) }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <div>
            <b style={{ color: C.text, fontSize: '13px' }}>Помещения и обмеры</b>
            <p style={{ color: C.textSec, fontSize: '12px', margin: '4px 0 0' }}>{projectRooms.length ? ('Полный обмер: ' + fullRooms + ' из ' + projectRooms.length + (missingRooms ? ' · дозаполнить: ' + missingRooms : '')) : 'Помещения ещё не заведены'}</p>
          </div>
          <button onClick={() => setActiveProjectTab('Помещения')} style={btnG}>Открыть помещения</button>
        </div>
      </div>

      {renderEstimateMeasurementComparisonPanel(project)}

      {docs.length === 0 && (
        <div style={{ ...card, padding: '28px', textAlign: 'center', color: C.textMuted }}>
          <FileText size={42} style={{ opacity: 0.35, marginBottom: '10px' }} />
          <p style={{ margin: 0 }}>Исходники проекта и обмеров пока не добавлены</p>
        </div>
      )}

      {docs.map(doc => {
        const sm = statusMeta(doc.status);
        const docDrafts = drafts.filter(d => Number(d.measurementId) === Number(doc.id));
        const docPhotos = String(doc.photoUrl || '').split(',').map(url => url.trim()).filter(Boolean);
        return (
          <div key={doc.id} style={{ ...card, padding: '14px', marginBottom: '10px', borderLeft: '4px solid ' + sm[0] }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: '220px' }}>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '6px' }}>
                  <span style={badge(sm[0], sm[1], sm[2])}>{doc.status}</span>
                  <span style={{ fontSize: '11px', color: C.textSec }}>{doc.sourceType + ' · ' + doc.docType}</span>
                </div>
                <b style={{ color: C.text, fontSize: '13px', display: 'block' }}>{doc.title || doc.docType}</b>
                <p style={{ color: C.textSec, fontSize: '12px', margin: '4px 0' }}>{(doc.uploadedBy ? 'Загрузил: ' + doc.uploadedBy : '') + (doc.createdAt ? ' · ' + String(doc.createdAt).slice(0, 10) : '') + (doc.roomsCreated ? (' · помещений: ' + doc.roomsCreated) : '')}</p>
                {doc.notes && <p style={{ color: C.textSec, fontSize: '12px', margin: '4px 0 0', lineHeight: 1.45 }}>{doc.notes}</p>}
                {docPhotos.length > 0 && (
                  <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginTop: '8px' }}>
                    {docPhotos.slice(0, 6).map((url, index) => (
                      <img key={url + index} src={fileSrc(url)} alt="" onClick={() => setShowPhotoModal(fileSrc(url))} style={{ width: '54px', height: '54px', objectFit: 'cover', borderRadius: '7px', cursor: 'pointer', border: '1px solid ' + C.border }} />
                    ))}
                    {docPhotos.length > 6 && <span style={{ fontSize: '11px', color: C.textSec, alignSelf: 'center' }}>+{docPhotos.length - 6}</span>}
                  </div>
                )}
                {doc.reviewedBy && <p style={{ color: C.success, fontSize: '11px', margin: '4px 0 0' }}>{'Принял: ' + doc.reviewedBy}</p>}
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                {doc.fileUrl && <a href={fileSrc(doc.fileUrl)} target="_blank" rel="noreferrer" style={{ ...btnB, padding: '5px 9px', fontSize: '11px', textDecoration: 'none' }}><Eye size={11} />Файл</a>}
                {canEditMeasurements && <button disabled={measurementDraftLoadingId === doc.id} onClick={() => generateRoomDrafts(doc)} style={{ ...btnB, padding: '5px 9px', fontSize: '11px', opacity: measurementDraftLoadingId === doc.id ? 0.7 : 1 }}><Bot size={11} />{measurementDraftLoadingId === doc.id ? 'Разбираю...' : 'ИИ разобрать'}</button>}
                {canEditMeasurements && doc.status !== 'На проверке' && <button onClick={() => updateMeasurement(doc, { status: 'На проверке' })} style={{ ...btnG, padding: '5px 9px', fontSize: '11px' }}>На проверку</button>}
                {canEditMeasurements && doc.status !== 'Принято' && <button onClick={() => updateMeasurement(doc, { status: 'Принято' })} style={{ ...btnGr, padding: '5px 9px', fontSize: '11px' }}>Принять</button>}
                {canEditMeasurements && doc.status !== 'Отклонено' && <button onClick={() => updateMeasurement(doc, { status: 'Отклонено' })} style={{ ...btnR, padding: '5px 9px', fontSize: '11px' }}>Отклонить</button>}
                {canEditMeasurements && <button onClick={() => deleteMeasurement(doc)} style={{ ...btnR, padding: '5px 9px', fontSize: '11px' }}><Trash2 size={11} /></button>}
              </div>
            </div>
            {docDrafts.length > 0 && (
              <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid ' + C.border }}>
                <b style={{ color: C.text, fontSize: '12px', display: 'block', marginBottom: '8px' }}>Черновики помещений из этого источника ({docDrafts.length})</b>
                <div style={{ display: 'grid', gap: '8px' }}>
                  {docDrafts.map(draft => {
                    const accepted = draft.acceptedRoomId || draft.status === 'Принято';
                    const rejected = draft.status === 'Отклонено';
                    const dColor = accepted ? C.success : rejected ? C.danger : C.info;
                    const dBg = accepted ? C.successLight : rejected ? C.dangerLight : C.infoLight;
                    const dBorder = accepted ? C.successBorder : rejected ? C.dangerBorder : C.infoBorder;
                    return (
                      <div key={draft.id} style={{ padding: '10px', borderRadius: '8px', backgroundColor: dBg, border: '1.5px solid ' + dBorder }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', flexWrap: 'wrap' }}>
                          <div style={{ flex: 1, minWidth: '210px' }}>
                            <span style={badge(dColor, dBg, dBorder)}>{draft.status || 'Черновик ИИ'}</span>
                            <b style={{ display: 'block', color: C.text, fontSize: '13px', marginTop: '5px' }}>{draft.name}</b>
                            <p style={{ color: C.textSec, fontSize: '12px', margin: '4px 0 0' }}>
                              {'Этаж ' + (draft.floor || 1) + (draft.roomType ? ' · ' + draft.roomType : '') +
                                ' · пол ' + fmtMeasure(draft.floorArea || 0, 'м2') +
                                (draft.wallArea ? (' · стены ' + fmtMeasure(draft.wallArea, 'м2')) : '') +
                                (draft.ceilingArea ? (' · потолок ' + fmtMeasure(draft.ceilingArea, 'м2')) : '') +
                                (draft.height ? (' · высота ' + fmtMeasure(draft.height, 'м')) : '') +
                                ((draft.windows || draft.doors) ? (' · окна ' + (draft.windows || 0) + ' / двери ' + (draft.doors || 0)) : '')}
                            </p>
                            {draft.notes && <p style={{ color: C.textMuted, fontSize: '11px', margin: '4px 0 0', lineHeight: 1.4 }}>{draft.notes}</p>}
                          </div>
                          {canEditMeasurements && (
                            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                              {!accepted && !rejected && <button onClick={() => acceptRoomDraft(draft)} style={{ ...btnGr, padding: '5px 9px', fontSize: '11px' }}><Check size={11} />В помещения</button>}
                              {!accepted && !rejected && <button onClick={() => rejectRoomDraft(draft)} style={{ ...btnR, padding: '5px 9px', fontSize: '11px' }}><X size={11} />Отклонить</button>}
                              {accepted && <button onClick={() => setActiveProjectTab('Помещения')} style={{ ...btnG, padding: '5px 9px', fontSize: '11px' }}>Открыть</button>}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
