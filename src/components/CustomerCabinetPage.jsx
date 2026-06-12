import React from 'react';
import { API } from '../api';
import ProjectHiddenWorksActSignatureModal from './ProjectHiddenWorksActSignatureModal';
import PreviewModal from './PreviewModal';
import ImagePreviewModal from './ImagePreviewModal';
import { Search, Eye, Check, X, Plus } from 'lucide-react';

export default function CustomerCabinetPage(props) {
  const {
    user,
    projects,
    handleLogout,
    C,
    card,
    btnG,
    btnB,
    btnO,
    btnGr,
    btnR,
    inp,
    listSearch,
    setListSearch,
    matchSearch,
    computeNotifications,
    workJournal,
    fmtMeasure,
    setShowPhotoModal,
    fileSrc,
    projectRealProgress,
    projectStages,
    hiddenActs,
    editingAct,
    setEditingAct,
    setHiddenActs,
    unexpectedWorksList,
    isApprovedEstimateChangeStatus,
    refreshData,
    showPreview,
    buildSupplementaryAgreementContent,
    activeEstimatesForProject,
    projectPlanDone,
    estimatePackage,
    sectionsOfEstimate,
    estimateItemMaterialSum,
    estimateItemTotal,
    showKS2,
    buildKS3Content,
    projectPayments,
    contracts,
    prescriptionsList,
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
            <span style={{ fontSize: '28px' }}>🏠</span>
            <div>
              <b style={{ color: C.text, fontSize: '18px', display: 'block' }}>Кабинет заказчика</b>
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
            <div style={{ ...card, padding: '20px', marginBottom: '16px', background: `linear-gradient(135deg,${C.accent},#5b6cf0)` }}>
              <b style={{ color: 'white', fontSize: '20px', display: 'block' }}>{myProject.name}</b>
              <p style={{ color: 'rgba(255,255,255,0.8)', margin: '4px 0 0', fontSize: '14px' }}>Статус: {myProject.status}</p>
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
                    <b style={{ color: C.text, fontSize: '14px' }}>👷 Что выполнено по объекту (последние 30 дней)</b>
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
                      {last30.length + ' работ'}
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
                      <b style={{ color: C.info, fontSize: '12px' }}>📅 Сегодня сделано: {todayList.length} работ</b>
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
                      placeholder="🔍 Поиск работы"
                      value={listSearch}
                      onChange={(e) => setListSearch(e.target.value)}
                      style={{ ...inp, marginBottom: 0, paddingLeft: '30px', fontSize: '12px', padding: '6px 8px 6px 30px' }}
                    />
                  </div>
                  <div style={{ maxHeight: '320px', overflowY: 'auto' }}>
                    {last30
                      .filter((entry) => matchSearch(listSearch, entry.description))
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
                              {entry.confirmedAt || entry.date || '—'}
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

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '12px', marginBottom: '16px' }}>
              <div style={{ ...card, padding: '16px', textAlign: 'center' }}>
                <p style={{ color: C.textSec, fontSize: '12px', margin: '0 0 4px' }}>Прогресс</p>
                <b style={{ color: C.accent, fontSize: '24px' }}>{projectRealProgress(myProject)}%</b>
                <div style={{ backgroundColor: C.bgGray, borderRadius: '6px', height: '6px', marginTop: '8px' }}>
                  <div
                    style={{
                      backgroundColor: C.accent,
                      width: `${projectRealProgress(myProject)}%`,
                      height: '100%',
                      borderRadius: '6px',
                    }}
                  />
                </div>
              </div>
              <div style={{ ...card, padding: '16px', textAlign: 'center' }}>
                <p style={{ color: C.textSec, fontSize: '12px', margin: '0 0 4px' }}>Бюджет</p>
                <b style={{ color: C.text, fontSize: '16px' }}>{Number(myProject.budget || 0).toLocaleString() + ' ₽'}</b>
              </div>
              <div style={{ ...card, padding: '16px', textAlign: 'center' }}>
                <p style={{ color: C.textSec, fontSize: '12px', margin: '0 0 4px' }}>Срок сдачи</p>
                <b style={{ color: C.text, fontSize: '14px' }}>{myProject.deadline || 'Не указан'}</b>
              </div>
            </div>

            <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>📋 Этапы</b>
              {projectStages
                .filter((stage) => stage.projectName === myProject.name)
                .map((stage) => (
                  <div
                    key={stage.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px 0',
                      borderBottom: `1px solid ${C.border}`,
                    }}
                  >
                    <div>
                      <b style={{ fontSize: '13px', color: C.text }}>{stage.name}</b>
                      <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>
                        {stage.startDate + ' — ' + stage.endDate}
                      </p>
                    </div>
                    <span
                      style={{
                        padding: '3px 8px',
                        borderRadius: '6px',
                        fontSize: '11px',
                        backgroundColor:
                          stage.status === 'Завершён'
                            ? C.successLight
                            : stage.status === 'В работе'
                              ? C.warningLight
                              : C.bg,
                        color:
                          stage.status === 'Завершён'
                            ? C.success
                            : stage.status === 'В работе'
                              ? C.warning
                              : C.textSec,
                      }}
                    >
                      {stage.status}
                    </span>
                  </div>
                ))}
              {projectStages.filter((stage) => stage.projectName === myProject.name).length === 0 && (
                <p style={{ color: C.textMuted, fontSize: '12px' }}>Этапы не добавлены</p>
              )}
            </div>

            <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>
                🔒 Акты освидетельствования скрытых работ (АОСР)
              </b>
              {(() => {
                const acts = hiddenActs.filter((act) => act.projectName === myProject.name);
                if (acts.length === 0) return <p style={{ color: C.textMuted, fontSize: '12px' }}>Актов пока нет. Появятся по ходу работ.</p>;
                const needSign = acts.filter((act) => !act.signedCustomer);
                return (
                  <div>
                    {needSign.length > 0 && (
                      <p style={{ color: C.warning, fontSize: '12px', marginBottom: '8px', fontWeight: '600' }}>
                        ⏳ {needSign.length} акт(ов) ждут моей подписи
                      </p>
                    )}
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
                            {Number(act.quantity || 0).toLocaleString('ru-RU') + ' ' + (act.unit || '') + ' · ' + (act.workDate || '')}
                          </p>
                        </div>
                        <span
                          style={{
                            padding: '2px 8px',
                            borderRadius: '10px',
                            fontSize: '10px',
                            fontWeight: '600',
                            backgroundColor: act.signedCustomer ? C.successLight : C.warningLight,
                            color: act.signedCustomer ? C.success : C.warning,
                          }}
                        >
                          {act.signedCustomer ? '✅ Я подписал' : '⏳ Ждёт моей подписи'}
                        </span>
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>

            <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>🆕 Изменения к смете</b>
              {(() => {
                const pending = (unexpectedWorksList || []).filter(
                  (row) => row.projectName === myProject.name && row.status === 'Ожидает согласования'
                );
                const approved = (unexpectedWorksList || []).filter(
                  (row) => row.projectName === myProject.name && isApprovedEstimateChangeStatus(row.status)
                );
                if (pending.length === 0 && approved.length === 0) {
                  return <p style={{ color: C.textMuted, fontSize: '12px' }}>Изменений нет — работаем по активной смете.</p>;
                }
                return (
                  <div>
                    {pending.length > 0 && (
                      <div style={{ marginBottom: '10px' }}>
                        <b style={{ color: C.warning, fontSize: '12px' }}>⏳ Ждут моего согласования ({pending.length}):</b>
                        {pending.map((row) => (
                          <div
                            key={row.id}
                            style={{
                              padding: '12px',
                              backgroundColor: '#fef3c7',
                              borderRadius: '8px',
                              marginTop: '6px',
                              border: '1.5px solid #fbbf24',
                            }}
                          >
                            <span
                              style={{
                                display: 'inline-block',
                                padding: '2px 8px',
                                borderRadius: '10px',
                                backgroundColor: 'rgba(249,115,22,.15)',
                                color: '#9a3412',
                                fontSize: '10px',
                                fontWeight: '700',
                                marginBottom: '4px',
                              }}
                            >
                              {row.changeType || 'Работа вне сметы'}
                            </span>
                            <b style={{ fontSize: '13px', color: '#78350f' }}>{row.description}</b>
                            <p style={{ color: '#78350f', margin: '4px 0', fontSize: '12px' }}>
                              {(row.quantity || 0) +
                                ' ' +
                                row.unit +
                                (row.price > 0 ? ' · ' + row.price.toLocaleString('ru-RU') + ' ₽/' + row.unit : '') +
                                (row.total > 0 ? ' · итого ' + row.total.toLocaleString('ru-RU') + ' ₽' : '')}
                            </p>
                            <p style={{ color: '#92400e', margin: '0 0 8px', fontSize: '11px' }}>
                              {'Запросил: ' + row.addedBy + (row.reason ? ' · Причина: ' + row.reason : '')}
                            </p>
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <button
                                onClick={async () => {
                                  if (!window.confirm(`Согласовать изменение «${row.description}» на ${(row.total || 0).toLocaleString('ru-RU')} ₽?`)) return;
                                  await fetch(`${API}/unexpected-works/${row.id}`, {
                                    method: 'PUT',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                      status: 'Утверждено отдельной допработой',
                                      price: row.price,
                                      total: row.total,
                                      approvedBy: user.name,
                                      approvedAt: new Date().toISOString().split('T')[0],
                                    }),
                                  });
                                  await refreshData();
                                  alert('Согласовано. Подрядчик может приступать.');
                                }}
                                style={{ ...btnGr, padding: '5px 10px', fontSize: '11px' }}
                              >
                                <Check size={11} />
                                Согласовать
                              </button>
                              <button
                                onClick={async () => {
                                  if (!window.confirm(`Отказать в выполнении «${row.description}»?`)) return;
                                  await fetch(`${API}/unexpected-works/${row.id}`, {
                                    method: 'PUT',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                      status: 'Отклонено',
                                      approvedBy: user.name,
                                      approvedAt: new Date().toISOString().split('T')[0],
                                    }),
                                  });
                                  await refreshData();
                                }}
                                style={{ ...btnR, padding: '5px 10px', fontSize: '11px' }}
                              >
                                <X size={11} />
                                Отказать
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    {approved.length > 0 && (
                      <div>
                        <b style={{ color: C.success, fontSize: '12px' }}>✅ Согласовано ранее ({approved.length}):</b>
                        {approved.slice(0, 5).map((row) => (
                          <div
                            key={row.id}
                            style={{
                              padding: '8px 12px',
                              backgroundColor: C.bg,
                              borderRadius: '6px',
                              marginTop: '4px',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              gap: '8px',
                              fontSize: '11px',
                            }}
                          >
                            <span style={{ color: C.textSec }}>
                              {row.description + ' · ' + (row.total || 0).toLocaleString('ru-RU') + ' ₽ · ' + row.approvedAt}
                            </span>
                            <button
                              onClick={() => showPreview(buildSupplementaryAgreementContent(row, myProject), 'Доп.соглашение № ' + row.id)}
                              style={{ ...btnB, padding: '3px 8px', fontSize: '10px' }}
                              title="Распечатать доп.соглашение"
                            >
                              <Eye size={10} />
                              📜
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>

            <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>📐 Смета объекта</b>
              {(() => {
                const activeEstimates = activeEstimatesForProject(myProject, 'Заказчик');
                const estimate = activeEstimates[0];
                if (activeEstimates.length === 0) {
                  return <p style={{ color: C.textMuted, fontSize: '12px' }}>Смета подрядчиком ещё не загружена.</p>;
                }
                const planDone = projectPlanDone(myProject);
                return (
                  <div>
                    <p style={{ color: C.text, fontSize: '13px', margin: '0 0 8px' }}>
                      <b>{activeEstimates.length === 1 ? estimate.name : 'Активные сметы: ' + activeEstimates.length}</b>
                      {activeEstimates.length === 1 ? ' · 📁 ' + estimatePackage(estimate) + ' · v' + (estimate.version || '1.0') : ''}
                    </p>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '10px' }}>
                      <div style={{ padding: '10px', backgroundColor: C.bg, borderRadius: '8px' }}>
                        <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>По смете</p>
                        <b style={{ color: C.text, fontSize: '14px' }}>{Math.round(planDone.plan).toLocaleString('ru-RU') + ' ₽'}</b>
                      </div>
                      <div style={{ padding: '10px', backgroundColor: C.successLight, borderRadius: '8px' }}>
                        <p style={{ color: C.success, fontSize: '11px', margin: '0 0 4px' }}>Выполнено</p>
                        <b style={{ color: C.success, fontSize: '14px' }}>{Math.round(planDone.done).toLocaleString('ru-RU') + ' ₽'}</b>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        let html =
                          '<h2>Сметы объекта</h2><p>Объект: ' +
                          myProject.name +
                          '</p><table><tr><th>Пакет</th><th>Раздел</th><th>Работа</th><th>Ед.</th><th>Кол-во</th><th>Цена работ</th><th>Материалы</th><th>Сумма</th></tr>';
                        activeEstimates.forEach((currentEstimate) =>
                          sectionsOfEstimate(currentEstimate).forEach((section) =>
                            (section.items || []).forEach((item) => {
                              html +=
                                '<tr><td>' +
                                estimatePackage(currentEstimate) +
                                '</td><td>' +
                                (section.name || '') +
                                '</td><td>' +
                                (item.name || '') +
                                '</td><td>' +
                                (item.unit || '') +
                                '</td><td>' +
                                (item.quantity || 0) +
                                '</td><td>' +
                                Number(item.priceWork || 0).toLocaleString('ru-RU') +
                                '</td><td>' +
                                Math.round(estimateItemMaterialSum(item)).toLocaleString('ru-RU') +
                                '</td><td>' +
                                Math.round(estimateItemTotal(item)).toLocaleString('ru-RU') +
                                '</td></tr>';
                            })
                          )
                        );
                        html +=
                          '<tr><td colspan=7><b>ИТОГО:</b></td><td><b>' +
                          Math.round(planDone.plan).toLocaleString('ru-RU') +
                          ' ₽</b></td></tr></table>';
                        showPreview(html, 'Сметы — ' + myProject.name);
                      }}
                      style={btnB}
                    >
                      <Eye size={14} />
                      📄 Посмотреть смету
                    </button>
                  </div>
                );
              })()}
            </div>

            <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>
                📄 Акты КС-2 и КС-3 на согласование
              </b>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button onClick={() => showKS2(myProject)} style={btnO}>
                  <Eye size={14} />
                  📄 КС-2 (приёмка работ)
                </button>
                <button onClick={() => showPreview(buildKS3Content(myProject), 'КС-3 — ' + myProject.name)} style={btnB}>
                  <Eye size={14} />
                  📋 КС-3 (стоимость)
                </button>
              </div>
              <p style={{ color: C.textMuted, fontSize: '11px', marginTop: '10px', lineHeight: 1.4 }}>
                Формируются автоматически из выполненных позиций активной сметы. Утверждённые изменения показываются
                отдельными разделами: дополнительные объёмы и работы вне сметы.
              </p>
            </div>

            <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>📷 Фото-отчёт</b>
              {(() => {
                const photos = workJournal.filter((entry) => entry.project === myProject.name && entry.photoUrl).slice(0, 12);
                if (photos.length === 0) {
                  return <p style={{ color: C.textMuted, fontSize: '12px' }}>Подрядчик пока не загружал фото работ.</p>;
                }
                return (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(80px,1fr))', gap: '6px' }}>
                    {photos.map((entry, idx) => {
                      const url = fileSrc(entry.photoUrl);
                      return (
                        <img
                          key={idx}
                          src={url}
                          alt=""
                          onClick={() => setShowPhotoModal(url)}
                          title={entry.description + ' · ' + entry.date}
                          style={{
                            width: '100%',
                            height: '80px',
                            borderRadius: '6px',
                            objectFit: 'cover',
                            cursor: 'pointer',
                            border: `1.5px solid ${C.border}`,
                          }}
                        />
                      );
                    })}
                  </div>
                );
              })()}
            </div>

            <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>
                📖 Журнал производства работ (последние 10)
              </b>
              {workJournal
                .filter((entry) => entry.project === myProject.name)
                .slice(0, 10)
                .map((entry) => (
                  <div key={entry.id} style={{ padding: '8px 0', borderBottom: `1px solid ${C.border}` }}>
                    <b style={{ fontSize: '12px', color: C.text }}>
                      {entry.description}
                      {entry.unexpectedWorkId ? (
                        <span title="Допработа" style={{ marginLeft: '4px' }}>
                          🆕
                        </span>
                      ) : null}
                      {entry.hiddenWork ? (
                        <span title="Скрытая работа" style={{ marginLeft: '4px' }}>
                          🔒
                        </span>
                      ) : null}
                    </b>
                    <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>
                      {(entry.masterName || '') + ' · ' + (entry.date || '') + ' · ' + (entry.status || '')}
                    </p>
                  </div>
                ))}
              {workJournal.filter((entry) => entry.project === myProject.name).length === 0 && (
                <p style={{ color: C.textMuted, fontSize: '12px' }}>Записей нет</p>
              )}
            </div>

            <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>⚠️ Мои замечания подрядчику</b>
              <textarea id="client_remark" placeholder="Опишите замечание..." style={{ ...inp, height: '70px' }} />
              <button
                onClick={async () => {
                  const text = document.getElementById('client_remark').value;
                  if (!text.trim()) return;
                  await fetch(`${API}/prescriptions`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      projectName: myProject.name,
                      violation: text,
                      priority: 'Замечание заказчика',
                      issuedBy: user.name,
                      issuedByRole: 'Заказчик',
                      status: 'Открыто',
                    }),
                  });
                  await refreshData();
                  document.getElementById('client_remark').value = '';
                  alert('Замечание передано подрядчику');
                }}
                style={btnO}
              >
                <Plus size={14} />
                Отправить
              </button>
              <div style={{ marginTop: '12px' }}>
                {(prescriptionsList || [])
                  .filter(
                    (prescription) =>
                      prescription.projectName === myProject.name &&
                      (prescription.issuedBy === user.name || prescription.issuedByRole === 'Заказчик')
                  )
                  .slice(0, 10)
                  .map((prescription) => (
                    <div
                      key={prescription.id}
                      style={{
                        padding: '8px 10px',
                        backgroundColor: C.bg,
                        borderRadius: '6px',
                        marginTop: '4px',
                        border: `1px solid ${C.border}`,
                      }}
                    >
                      <b style={{ fontSize: '12px', color: C.text }}>
                        {prescription.violation || prescription.description || '(пусто)'}
                      </b>
                      <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>
                        {(prescription.status || '') + (prescription.deadline ? ' · до ' + prescription.deadline : '')}
                      </p>
                    </div>
                  ))}
              </div>
            </div>

            <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>💰 Платежи по объекту</b>
              {(() => {
                const payments = (projectPayments || []).filter((row) => row.projectName === myProject.name);
                const paid = payments.reduce((sum, row) => sum + Number(row.amount || 0), 0);
                const budget = Number(myProject.budget || 0);
                const remain = budget - paid;
                return (
                  <div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '8px', marginBottom: '10px' }}>
                      <div style={{ padding: '10px', backgroundColor: C.bg, borderRadius: '8px' }}>
                        <p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 4px' }}>Бюджет</p>
                        <b style={{ color: C.text, fontSize: '13px' }}>{Math.round(budget).toLocaleString('ru-RU') + ' ₽'}</b>
                      </div>
                      <div style={{ padding: '10px', backgroundColor: C.successLight, borderRadius: '8px' }}>
                        <p style={{ color: C.success, fontSize: '10px', margin: '0 0 4px' }}>Оплачено</p>
                        <b style={{ color: C.success, fontSize: '13px' }}>{Math.round(paid).toLocaleString('ru-RU') + ' ₽'}</b>
                      </div>
                      <div style={{ padding: '10px', backgroundColor: C.warningLight, borderRadius: '8px' }}>
                        <p style={{ color: C.warning, fontSize: '10px', margin: '0 0 4px' }}>Остаток</p>
                        <b style={{ color: C.warning, fontSize: '13px' }}>{Math.round(remain).toLocaleString('ru-RU') + ' ₽'}</b>
                      </div>
                    </div>
                    {payments.slice(0, 8).map((payment, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '6px 10px',
                          backgroundColor: C.bg,
                          borderRadius: '6px',
                          marginTop: '4px',
                          display: 'flex',
                          justifyContent: 'space-between',
                          fontSize: '11px',
                        }}
                      >
                        <span>{(payment.date || '') + (payment.note ? ' · ' + payment.note : '')}</span>
                        <b style={{ color: C.success }}>{Math.round(Number(payment.amount || 0)).toLocaleString('ru-RU') + ' ₽'}</b>
                      </div>
                    ))}
                    {payments.length === 0 && (
                      <p style={{ color: C.textMuted, fontSize: '11px', textAlign: 'center', padding: '8px' }}>Платежей пока нет</p>
                    )}
                  </div>
                );
              })()}
            </div>

            <div style={{ ...card, padding: '20px' }}>
              <b style={{ color: C.text, fontSize: '14px', display: 'block', marginBottom: '12px' }}>📄 Договоры</b>
              {contracts
                .filter((contract) => contract.projectName === myProject.name || contract.client === user.name)
                .map((contract) => (
                  <div
                    key={contract.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px 0',
                      borderBottom: `1px solid ${C.border}`,
                    }}
                  >
                    <div>
                      <b style={{ fontSize: '13px', color: C.text }}>Договор № {contract.number}</b>
                      <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>
                        {Number(contract.totalAmount || 0).toLocaleString() + ' ₽ · ' + contract.status}
                      </p>
                    </div>
                    <button
                      onClick={() =>
                        showPreview(
                          `<h2>Договор №${contract.number}</h2><p>Заказчик: ${contract.client}</p><p>Сумма: ${Number(contract.totalAmount || 0).toLocaleString()} ₽</p>`,
                          'Договор'
                        )
                      }
                      style={{ ...btnB, padding: '4px 10px', fontSize: '11px' }}
                    >
                      <Eye size={11} />
                      Открыть
                    </button>
                  </div>
                ))}
              {contracts.filter((contract) => contract.projectName === myProject.name || contract.client === user.name).length === 0 && (
                <p style={{ color: C.textMuted, fontSize: '12px' }}>Договоров нет</p>
              )}
            </div>
          </div>
        )}
      </div>
      <ProjectHiddenWorksActSignatureModal
        act={editingAct}
        mode="customer"
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
