import React from 'react';
import { API } from '../api';
import ProjectHiddenWorksActSignatureModal from './ProjectHiddenWorksActSignatureModal';
import PreviewModal from './PreviewModal';
import ImagePreviewModal from './ImagePreviewModal';
import { Search, Eye, Check, Plus, Upload, ChevronRight } from 'lucide-react';
import { createSupervisorActForm } from '../features/documents/projectDocumentInitialForms';

export default function SupervisorCabinetPage(props) {
  const {
    user,
    projects,
    handleLogout,
    C,
    card,
    btnG,
    btnB,
    btnO,
    inp,
    listSearch,
    setListSearch,
    matchSearch,
    projectRealProgress,
    projectPlanDone,
    showPreview,
    buildSupervisorMonthlyReport,
    computeNotifications,
    workJournal,
    fmtMeasure,
    setShowPhotoModal,
    fileSrc,
    checklists,
    prescriptionsList,
    buildPrescriptionContent,
    prescriptionPhoto,
    setPrescriptionPhoto,
    appendPhotos,
    refreshData,
    showForm,
    setShowForm,
    newSupervisorAct,
    setNewSupervisorAct,
    supervisorActPhoto,
    setSupervisorActPhoto,
    supervisorActs,
    materialInspections,
    hiddenActs,
    editingAct,
    setEditingAct,
    setHiddenActs,
    showPhotoModal,
    previewContent,
    previewTitle,
    setPreviewContent,
    doPrint,
  } = props;

  const myProject = projects.find(
    (project) =>
      project.id === Number(user.project_id || user.projectId) ||
      project.name === (user.project_name || user.projectName)
  );

  return (
    <div style={{ minHeight: '100vh', backgroundColor: C.bg, padding: '20px' }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '28px' }}>🔎</span>
            <div>
              <b style={{ color: C.text, fontSize: '18px', display: 'block' }}>Технический надзор</b>
              <p style={{ color: C.textSec, margin: 0, fontSize: '13px' }}>{user.name}</p>
            </div>
          </div>
          <button onClick={() => handleLogout()} style={{ ...btnG, fontSize: '12px' }}>
            Выйти
          </button>
        </div>

        {!myProject ? (
          <div style={{ ...card, padding: '40px', textAlign: 'center' }}>
            <p style={{ color: C.textMuted }}>Объект не найден. Обратитесь к подрядчику.</p>
          </div>
        ) : (
          <div>
            <div
              style={{
                ...card,
                padding: '16px',
                marginBottom: '16px',
                backgroundColor: C.accentLight,
                border: `1.5px solid ${C.accentBorder}`,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <div>
                  <b style={{ color: C.text, fontSize: '16px' }}>{myProject.name}</b>
                  <p style={{ color: C.textSec, margin: '4px 0 0', fontSize: '13px' }}>
                    {'Статус: ' + myProject.status}
                    {' · Прогресс: ' + projectRealProgress(myProject) + '%'}
                    {' · Выполнено: ' + Math.round(projectPlanDone(myProject).done).toLocaleString('ru-RU') + ' ₽'}
                  </p>
                </div>
                <button
                  onClick={() => {
                    const today = new Date();
                    const monthAgo = new Date(today.getTime() - 30 * 24 * 3600 * 1000);
                    showPreview(
                      buildSupervisorMonthlyReport(
                        myProject.name,
                        monthAgo.toISOString().split('T')[0],
                        today.toISOString().split('T')[0]
                      ),
                      'Месячный отчёт технадзора'
                    );
                  }}
                  style={btnB}
                >
                  <Eye size={14} />
                  📊 Месячный отчёт
                </button>
              </div>
            </div>

            {(() => {
              const notifs = computeNotifications();
              if (notifs.length === 0) return null;
              return (
                <div style={{ marginBottom: '16px' }}>
                  {notifs.slice(0, 5).map((notification, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '10px 12px',
                        backgroundColor: 'rgba(251,191,36,0.12)',
                        border: `1.5px solid ${notification.color}`,
                        borderRadius: '10px',
                        marginBottom: '6px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                      }}
                    >
                      <span style={{ fontSize: '18px' }}>{notification.icon}</span>
                      <div>
                        <b style={{ fontSize: '12px', color: C.text, display: 'block' }}>{notification.title}</b>
                        <span style={{ fontSize: '11px', color: C.textSec }}>{notification.text}</span>
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}

            {(() => {
              const confirmedJournal = (workJournal || []).filter(
                (entry) => entry.project === myProject.name && entry.status === 'Подтверждено'
              );
              const last30 = confirmedJournal.filter((entry) => {
                const date = new Date(entry.confirmedAt || entry.date || 0);
                return Date.now() - date.getTime() < 30 * 24 * 3600 * 1000;
              });
              if (confirmedJournal.length === 0) return null;
              const today = new Date().toISOString().split('T')[0];
              const todayList = confirmedJournal.filter(
                (entry) => (entry.confirmedAt || entry.date || '').split('T')[0] === today
              );
              return (
                <div style={{ ...card, padding: '16px', marginBottom: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
                    <b style={{ color: C.text, fontSize: '14px' }}>👷 Принятые работы (последние 30 дней)</b>
                    <span
                      style={{
                        padding: '3px 10px',
                        borderRadius: '10px',
                        backgroundColor: C.successLight,
                        color: C.success,
                        fontSize: '12px',
                        fontWeight: '700',
                      }}
                    >
                      {last30.length + ' шт'}
                    </span>
                  </div>
                  {todayList.length > 0 && (
                    <div
                      style={{
                        padding: '8px 10px',
                        marginBottom: '10px',
                        borderRadius: '8px',
                        backgroundColor: C.infoLight,
                        border: `1.5px solid ${C.infoBorder}`,
                      }}
                    >
                      <b style={{ color: C.info, fontSize: '12px' }}>📅 Сегодня принято: {todayList.length} раб.</b>
                    </div>
                  )}
                  <div style={{ position: 'relative', marginBottom: '8px' }}>
                    <Search
                      size={13}
                      style={{
                        position: 'absolute',
                        left: '10px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        color: C.textMuted,
                      }}
                    />
                    <input
                      placeholder="🔍 Поиск работы или мастера"
                      value={listSearch}
                      onChange={(e) => setListSearch(e.target.value)}
                      style={{ ...inp, marginBottom: 0, paddingLeft: '30px', fontSize: '12px', padding: '6px 8px 6px 30px' }}
                    />
                  </div>
                  <div style={{ maxHeight: '320px', overflowY: 'auto' }}>
                    {last30
                      .filter((entry) => matchSearch(listSearch, entry.description, entry.masterName || entry.master_name))
                      .slice(0, 30)
                      .map((entry) => (
                        <div
                          key={entry.id}
                          style={{
                            padding: '8px 0',
                            borderBottom: `1px solid ${C.border}`,
                            display: 'flex',
                            justifyContent: 'space-between',
                            gap: '8px',
                          }}
                        >
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <b style={{ fontSize: '12px', color: C.text, display: 'block' }}>{entry.description}</b>
                            <p style={{ color: C.textSec, margin: '2px 0 0', fontSize: '11px' }}>
                              {(entry.masterName || entry.master_name || '—') + ' · ' + (entry.confirmedAt || entry.date || '—')}
                            </p>
                          </div>
                          <div style={{ textAlign: 'right', flexShrink: 0 }}>
                            <b style={{ fontSize: '12px', color: C.text }}>{fmtMeasure(entry.quantity, entry.unit)}</b>
                            {entry.photoUrl && (
                              <button
                                onClick={() => setShowPhotoModal(fileSrc(entry.photoUrl))}
                                style={{ ...btnG, padding: '2px 6px', fontSize: '10px', marginLeft: '4px' }}
                              >
                                📷
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              );
            })()}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
              <div style={{ ...card, padding: '16px' }}>
                <b style={{ color: C.text, fontSize: '13px', display: 'block', marginBottom: '10px' }}>📋 Чек-листы</b>
                {checklists
                  .filter((checklist) => checklist.projectName === myProject.name)
                  .map((checklist) => (
                    <div key={checklist.id} style={{ padding: '8px 0', borderBottom: `1px solid ${C.border}` }}>
                      <b style={{ fontSize: '12px', color: C.text }}>{checklist.name}</b>
                      <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>{checklist.status}</p>
                    </div>
                  ))}
                {checklists.filter((checklist) => checklist.projectName === myProject.name).length === 0 && (
                  <p style={{ color: C.textMuted, fontSize: '12px' }}>Нет чек-листов</p>
                )}
              </div>
              <div style={{ ...card, padding: '16px' }}>
                <b style={{ color: C.text, fontSize: '13px', display: 'block', marginBottom: '10px' }}>⚠️ Предписания</b>
                {prescriptionsList
                  .filter((prescription) => prescription.projectName === myProject.name)
                  .map((prescription) => (
                    <div key={prescription.id} style={{ padding: '8px 0', borderBottom: `1px solid ${C.border}` }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '6px' }}>
                        <div style={{ flex: 1 }}>
                          <b style={{ fontSize: '12px', color: C.danger }}>
                            {prescription.violation || prescription.description || '(описание не указано)'}
                          </b>
                          <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>
                            {(prescription.priority ? `${prescription.priority} · ` : '') +
                              (prescription.status || 'Открыто') +
                              (prescription.deadline ? ` · до ${prescription.deadline}` : '')}
                          </p>
                        </div>
                        <button
                          onClick={() => showPreview(buildPrescriptionContent(prescription), 'Предписание')}
                          style={{ ...btnB, padding: '4px 8px', fontSize: '11px' }}
                          title="Распечатать предписание"
                        >
                          🖨️
                        </button>
                      </div>
                      {prescription.photoUrl && (
                        <img
                          src={fileSrc(prescription.photoUrl)}
                          alt=""
                          onClick={() => setShowPhotoModal(fileSrc(prescription.photoUrl))}
                          style={{
                            width: '48px',
                            height: '48px',
                            borderRadius: '6px',
                            objectFit: 'cover',
                            cursor: 'pointer',
                            marginTop: '4px',
                          }}
                        />
                      )}
                    </div>
                  ))}
                {prescriptionsList.filter((prescription) => prescription.projectName === myProject.name).length === 0 && (
                  <p style={{ color: C.textMuted, fontSize: '12px' }}>Предписаний нет</p>
                )}
              </div>
            </div>

            <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>⚠️ Выдать предписание</b>
              <textarea id="pres_desc_tn" placeholder="Описание нарушения *" style={{ ...inp, height: '80px' }} />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <select id="pres_priority_tn" style={{ ...inp, marginBottom: 0 }}>
                  <option value="Критичное">🔴 Критичное</option>
                  <option value="Важное">🟡 Важное</option>
                  <option value="Замечание">🟢 Замечание</option>
                </select>
                <input
                  type="date"
                  id="pres_date_tn"
                  style={{ ...inp, marginBottom: 0 }}
                  defaultValue={new Date().toISOString().split('T')[0]}
                />
              </div>
              <div style={{ marginTop: '10px' }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '6px' }}>
                  <label style={{ ...btnB, padding: '8px 12px', fontSize: '12px', cursor: 'pointer' }}>
                    <Upload size={12} />
                    📷 Прикрепить фото (можно несколько)
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      style={{ display: 'none' }}
                      onChange={async (e) => {
                        if (e.target.files && e.target.files.length > 0) {
                          const csv = await appendPhotos(prescriptionPhoto, e.target.files, {
                            projectName: myProject.name,
                            context: 'prescriptions',
                          });
                          setPrescriptionPhoto(csv);
                          e.target.value = '';
                        }
                      }}
                    />
                  </label>
                  {(prescriptionPhoto || '').split(',').filter(Boolean).length > 0 && (
                    <span style={{ fontSize: '11px', color: C.success, fontWeight: '600' }}>
                      📷 {(prescriptionPhoto || '').split(',').filter(Boolean).length} фото
                    </span>
                  )}
                </div>
                {(() => {
                  const urls = (prescriptionPhoto || '').split(',').filter(Boolean);
                  if (urls.length === 0) return null;
                  return (
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                      {urls.map((url, idx) => (
                        <div key={idx} style={{ position: 'relative' }}>
                          <img
                            src={fileSrc(url)}
                            alt=""
                            onClick={() => setShowPhotoModal(fileSrc(url))}
                            style={{
                              width: '60px',
                              height: '60px',
                              objectFit: 'cover',
                              borderRadius: '6px',
                              cursor: 'pointer',
                              border: `1px solid ${C.border}`,
                            }}
                          />
                          <button
                            type="button"
                            onClick={(ev) => {
                              ev.preventDefault();
                              ev.stopPropagation();
                              setPrescriptionPhoto(urls.filter((_, innerIdx) => innerIdx !== idx).join(','));
                            }}
                            style={{
                              position: 'absolute',
                              top: '-4px',
                              right: '-4px',
                              background: 'rgba(220,38,38,0.9)',
                              color: 'white',
                              border: 'none',
                              borderRadius: '50%',
                              width: '18px',
                              height: '18px',
                              cursor: 'pointer',
                              fontSize: '10px',
                              lineHeight: '1',
                              padding: 0,
                            }}
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  );
                })()}
              </div>
              <button
                onClick={async () => {
                  const description = document.getElementById('pres_desc_tn').value;
                  if (!description) {
                    alert('Введите описание');
                    return;
                  }
                  const priority = document.getElementById('pres_priority_tn').value;
                  const deadline = document.getElementById('pres_date_tn').value;
                  await fetch(`${API}/prescriptions`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      projectName: myProject.name,
                      violation: description,
                      priority,
                      deadline,
                      issuedBy: user.name,
                      issuedByRole: 'Технадзор',
                      status: 'Открыто',
                      photoUrl: prescriptionPhoto,
                    }),
                  });
                  await refreshData();
                  document.getElementById('pres_desc_tn').value = '';
                  setPrescriptionPhoto('');
                  alert('Предписание выдано!');
                }}
                style={{ ...btnO, marginTop: '12px' }}
              >
                <Plus size={14} />
                Выдать предписание
              </button>
            </div>

            <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>
                🔒 Акты освидетельствования скрытых работ (АОСР)
              </b>
              {(() => {
                const acts = hiddenActs.filter((act) => act.projectName === myProject.name);
                if (acts.length === 0) {
                  return (
                    <p style={{ color: C.textMuted, fontSize: '12px' }}>
                      АОСР пока нет — появятся когда мастер закроет позиции 🔒 в смете объекта.
                    </p>
                  );
                }
                return (
                  <div>
                    {acts.slice(0, 10).map((act) => (
                      <div
                        key={act.id}
                        onClick={() => setEditingAct(act)}
                        style={{
                          padding: '10px 12px',
                          backgroundColor: C.bg,
                          borderRadius: '8px',
                          marginBottom: '6px',
                          border: `1.5px solid ${C.border}`,
                          cursor: 'pointer',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          gap: '8px',
                        }}
                      >
                        <div style={{ flex: 1, overflow: 'hidden' }}>
                          <b style={{ fontSize: '12px', color: C.text }}>{`${act.actNumber} · ${act.workName}`}</b>
                          <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>
                            {(act.quantity || 0) + ' ' + (act.unit || '') + ' · ' + (act.workDate || '')}
                          </p>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                          {act.signedSupervisor ? (
                            <span
                              style={{
                                padding: '2px 8px',
                                borderRadius: '10px',
                                fontSize: '10px',
                                fontWeight: '600',
                                backgroundColor: C.successLight,
                                color: C.success,
                              }}
                            >
                              ✅ Я подписал
                            </span>
                          ) : (
                            <span
                              style={{
                                padding: '2px 8px',
                                borderRadius: '10px',
                                fontSize: '10px',
                                fontWeight: '600',
                                backgroundColor: C.warningLight,
                                color: C.warning,
                              }}
                            >
                              ⏳ Ждёт моей подписи
                            </span>
                          )}
                          <ChevronRight size={14} color={C.textMuted} />
                        </div>
                      </div>
                    ))}
                    <p style={{ fontSize: '11px', color: C.textMuted, marginTop: '8px' }}>
                      Клик по строке → откроется карточка акта. В поле «Технадзор» впиши свои ФИО и дату, сохрани —
                      подпись зафиксируется.
                    </p>
                  </div>
                );
              })()}
            </div>

            <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <b style={{ color: C.text, fontSize: '14px' }}>📝 Мои акты осмотра / обследования</b>
                <button onClick={() => setShowForm(showForm === 'svact' ? false : 'svact')} style={{ ...btnO, padding: '5px 10px', fontSize: '11px' }}>
                  <Plus size={11} />
                  Новый акт
                </button>
              </div>
              {showForm === 'svact' && (
                <div
                  style={{
                    padding: '12px',
                    backgroundColor: C.bg,
                    borderRadius: '8px',
                    marginBottom: '10px',
                    border: `1.5px solid ${C.border}`,
                  }}
                >
                  <select
                    value={newSupervisorAct.actType}
                    onChange={(e) => setNewSupervisorAct({ ...newSupervisorAct, actType: e.target.value })}
                    style={{ ...inp, marginBottom: '8px' }}
                  >
                    <option>Осмотр</option>
                    <option>Обследование</option>
                    <option>Акт промежуточной приёмки</option>
                    <option>Акт по результатам контроля</option>
                  </select>
                  <textarea
                    placeholder="Предмет осмотра (что проверяли)"
                    value={newSupervisorAct.description}
                    onChange={(e) => setNewSupervisorAct({ ...newSupervisorAct, description: e.target.value })}
                    style={{ ...inp, minHeight: '60px', marginBottom: '8px' }}
                  />
                  <textarea
                    placeholder="Результат / что обнаружили"
                    value={newSupervisorAct.findings}
                    onChange={(e) => setNewSupervisorAct({ ...newSupervisorAct, findings: e.target.value })}
                    style={{ ...inp, minHeight: '60px', marginBottom: '8px' }}
                  />
                  <textarea
                    placeholder="Рекомендации / требования"
                    value={newSupervisorAct.recommendations}
                    onChange={(e) => setNewSupervisorAct({ ...newSupervisorAct, recommendations: e.target.value })}
                    style={{ ...inp, minHeight: '50px', marginBottom: '8px' }}
                  />
                  <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', alignItems: 'center' }}>
                    <input
                      type="date"
                      value={newSupervisorAct.date}
                      onChange={(e) => setNewSupervisorAct({ ...newSupervisorAct, date: e.target.value })}
                      style={{ ...inp, marginBottom: 0, flex: 1 }}
                    />
                    <label style={{ ...btnB, padding: '8px 12px', fontSize: '12px', cursor: 'pointer' }}>
                      <Upload size={12} />
                      📷 Фото (можно несколько)
                      <input
                        type="file"
                        accept="image/*"
                        multiple
                        style={{ display: 'none' }}
                        onChange={async (e) => {
                          if (e.target.files && e.target.files.length > 0) {
                            const csv = await appendPhotos(supervisorActPhoto, e.target.files, {
                              projectName: myProject.name,
                              context: 'supervisor-acts',
                            });
                            setSupervisorActPhoto(csv);
                            e.target.value = '';
                          }
                        }}
                      />
                    </label>
                    {(supervisorActPhoto || '').split(',').filter(Boolean).length > 0 && (
                      <span style={{ fontSize: '11px', color: C.success, fontWeight: '600' }}>
                        {(supervisorActPhoto || '').split(',').filter(Boolean).length}
                      </span>
                    )}
                  </div>
                  {(() => {
                    const urls = (supervisorActPhoto || '').split(',').filter(Boolean);
                    if (urls.length === 0) return null;
                    return (
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '8px' }}>
                        {urls.map((url, idx) => (
                          <div key={idx} style={{ position: 'relative' }}>
                            <img
                              src={fileSrc(url)}
                              alt=""
                              onClick={() => setShowPhotoModal(fileSrc(url))}
                              style={{
                                width: '60px',
                                height: '60px',
                                objectFit: 'cover',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                border: `1px solid ${C.border}`,
                              }}
                            />
                            <button
                              type="button"
                              onClick={(ev) => {
                                ev.preventDefault();
                                ev.stopPropagation();
                                setSupervisorActPhoto(urls.filter((_, innerIdx) => innerIdx !== idx).join(','));
                              }}
                              style={{
                                position: 'absolute',
                                top: '-4px',
                                right: '-4px',
                                background: 'rgba(220,38,38,0.9)',
                                color: 'white',
                                border: 'none',
                                borderRadius: '50%',
                                width: '18px',
                                height: '18px',
                                cursor: 'pointer',
                                fontSize: '10px',
                                lineHeight: '1',
                                padding: 0,
                              }}
                            >
                              ×
                            </button>
                          </div>
                        ))}
                      </div>
                    );
                  })()}
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={async () => {
                        if (!newSupervisorAct.description) {
                          alert('Опишите предмет осмотра');
                          return;
                        }
                        await fetch(`${API}/supervisor-acts`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            projectName: myProject.name,
                            actType: newSupervisorAct.actType,
                            description: newSupervisorAct.description,
                            findings: newSupervisorAct.findings,
                            recommendations: newSupervisorAct.recommendations,
                            issuedBy: user.name,
                            issuedByRole: 'Технадзор',
                            photoUrl: supervisorActPhoto,
                            date: newSupervisorAct.date || new Date().toISOString().split('T')[0],
                          }),
                        });
                        await refreshData();
                        setNewSupervisorAct(createSupervisorActForm());
                        setSupervisorActPhoto('');
                        setShowForm(false);
                        alert('Акт сохранён');
                      }}
                      style={btnO}
                    >
                      <Check size={14} />
                      Сохранить
                    </button>
                    <button
                      onClick={() => {
                        setShowForm(false);
                        setNewSupervisorAct(createSupervisorActForm());
                        setSupervisorActPhoto('');
                      }}
                      style={btnG}
                    >
                      Отмена
                    </button>
                  </div>
                </div>
              )}
              {(() => {
                const acts = supervisorActs.filter((act) => act.projectName === myProject.name);
                if (acts.length === 0) {
                  return (
                    <p style={{ color: C.textMuted, fontSize: '12px' }}>
                      Актов осмотра пока нет. Нажми «Новый акт» чтобы зафиксировать обследование.
                    </p>
                  );
                }
                return acts.slice(0, 10).map((act) => (
                  <div
                    key={act.id}
                    style={{
                      padding: '10px',
                      backgroundColor: C.bg,
                      borderRadius: '8px',
                      marginBottom: '6px',
                      border: `1.5px solid ${C.border}`,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                      <div style={{ flex: 1 }}>
                        <b style={{ fontSize: '12px', color: C.text }}>{`${act.actNumber} · ${act.actType}`}</b>
                        <p style={{ color: C.textSec, margin: '4px 0 0', fontSize: '11px' }}>{act.description}</p>
                        {act.findings && (
                          <p style={{ color: C.text, margin: '4px 0 0', fontSize: '11px' }}>
                            <b>Обнаружено:</b> {act.findings}
                          </p>
                        )}
                        {act.recommendations && (
                          <p style={{ color: C.text, margin: '4px 0 0', fontSize: '11px' }}>
                            <b>Рекомендации:</b> {act.recommendations}
                          </p>
                        )}
                        <p style={{ color: C.textMuted, margin: '4px 0 0', fontSize: '10px' }}>{act.date}</p>
                      </div>
                      {act.photoUrl && (
                        <img
                          src={fileSrc(act.photoUrl)}
                          alt=""
                          onClick={() => setShowPhotoModal(fileSrc(act.photoUrl))}
                          style={{ width: '56px', height: '56px', borderRadius: '6px', objectFit: 'cover', cursor: 'pointer', flexShrink: 0 }}
                        />
                      )}
                    </div>
                  </div>
                ));
              })()}
            </div>

            <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>📦 Входной контроль материалов</b>
              {(() => {
                const rows = materialInspections.filter((row) => row.projectName === myProject.name);
                if (rows.length === 0) {
                  return (
                    <p style={{ color: C.textMuted, fontSize: '12px' }}>
                      Записей нет. Появятся когда подрядчик примет накладную на материал.
                    </p>
                  );
                }
                const pending = rows.filter((row) => !row.inspected).length;
                return (
                  <div>
                    {pending > 0 && (
                      <p style={{ color: C.warning, fontSize: '12px', marginBottom: '8px' }}>
                        ⏳ {pending} материала ждут отметки о входном контроле
                      </p>
                    )}
                    {rows.slice(0, 8).map((row) => (
                      <div
                        key={row.id}
                        style={{
                          padding: '8px 10px',
                          backgroundColor: C.bg,
                          borderRadius: '6px',
                          marginBottom: '4px',
                          border: `1px solid ${C.border}`,
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <div style={{ flex: 1, overflow: 'hidden' }}>
                          <b style={{ fontSize: '11px', color: C.text }}>{row.materialName}</b>
                          <p style={{ color: C.textSec, margin: '2px 0', fontSize: '10px' }}>
                            {(row.quantity || 0) + ' ' + (row.unit || '') + ' · ' + (row.supplier || '—') + ' · ' + (row.receivedAt || '')}
                          </p>
                        </div>
                        <span
                          style={{
                            padding: '2px 8px',
                            borderRadius: '10px',
                            fontSize: '10px',
                            fontWeight: '600',
                            backgroundColor: row.inspected ? C.successLight : C.warningLight,
                            color: row.inspected ? C.success : C.warning,
                          }}
                        >
                          {row.inspected ? '✅' : '⏳'}
                        </span>
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>

            <div style={{ ...card, padding: '20px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>📖 Журнал работ</b>
              {workJournal
                .filter((entry) => entry.project === myProject.name)
                .slice(0, 10)
                .map((entry) => (
                  <div key={entry.id} style={{ padding: '8px 0', borderBottom: `1px solid ${C.border}` }}>
                    <b style={{ fontSize: '12px', color: C.text }}>{entry.description}</b>
                    <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>
                      {entry.masterName + ' · ' + entry.date + ' · ' + entry.status}
                    </p>
                  </div>
                ))}
              {workJournal.filter((entry) => entry.project === myProject.name).length === 0 && (
                <p style={{ color: C.textMuted, fontSize: '12px' }}>Записей нет</p>
              )}
            </div>
          </div>
        )}
      </div>
      <ProjectHiddenWorksActSignatureModal
        act={editingAct}
        mode="supervisor"
        setEditingAct={setEditingAct}
        setHiddenActs={setHiddenActs}
        C={C}
        card={card}
        inp={inp}
        btnG={btnG}
        btnO={btnO}
      />
      <ImagePreviewModal src={showPhotoModal} onClose={() => setShowPhotoModal(null)} />
      {previewContent && (
        <PreviewModal
          content={previewContent}
          title={previewTitle}
          onClose={() => setPreviewContent(null)}
          onPrint={doPrint}
        />
      )}
    </div>
  );
}
