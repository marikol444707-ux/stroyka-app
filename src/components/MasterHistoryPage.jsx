import React from 'react';
import { ChevronDown, ChevronUp, Search } from 'lucide-react';

export default function MasterHistoryPage({
  C,
  btnG,
  card,
  expandedProject,
  fileSrc,
  fmtMeasure,
  listSearch,
  matchSearch,
  myJournal,
  piecework,
  setExpandedProject,
  setListSearch,
  setShowPhotoModal,
  sumConfirmed,
  user,
}) {
  const toNumber = (value) => {
    const parsed = Number(String(value ?? 0).replace(',', '.').replace(/\s+/g, ''));
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const workAmount = (work) => {
    const executionTotal = toNumber(work.executionTotal ?? work.execution_total);
    if (executionTotal > 0) return executionTotal;
    return toNumber(work.total);
  };
  const workStatus = (work) => work.status || 'На проверке';
  const confirmedTotal = (myJournal || [])
    .filter((work) => workStatus(work) === 'Подтверждено')
    .reduce((sum, work) => sum + workAmount(work), 0);
  const acceptedTotal = confirmedTotal || toNumber(sumConfirmed);

  return (
    <div>
      <h3 style={{ color: C.text, marginBottom: '14px', fontSize: '18px', fontWeight: '700' }}>📅 История работ по дням</h3>
      <div style={{ background: 'linear-gradient(135deg,#f97316,#ea580c)', padding: '16px 20px', borderRadius: '12px', marginBottom: '14px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
        <div>
          <p style={{ color: 'rgba(255,255,255,0.85)', fontSize: '11px', margin: 0 }}>Принято всего</p>
          <b style={{ color: 'white', fontSize: '18px' }}>{Math.round(acceptedTotal).toLocaleString('ru-RU') + ' ₽'}</b>
        </div>
        <div style={{ textAlign: 'right' }}>
          <p style={{ color: 'rgba(255,255,255,0.85)', fontSize: '11px', margin: 0 }}>Зачислено к выплате</p>
          <b style={{ color: 'white', fontSize: '18px' }}>
            {Math.round((piecework || []).filter((pw) => Number(pw.staffId) === user.id).reduce((sum, pw) => sum + Number(pw.total || 0), 0)).toLocaleString('ru-RU') + ' ₽'}
          </b>
        </div>
      </div>

      <div style={{ position: 'relative', marginBottom: '14px' }}>
        <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: C.textMuted }} />
        <input placeholder="🔍 Поиск работы или объекта" value={listSearch} onChange={(e) => setListSearch(e.target.value)} style={{ ...C.inp, marginBottom: 0, paddingLeft: '32px' }} />
      </div>

      {(() => {
        const filtered = myJournal.filter((work) => matchSearch(listSearch, work.description, work.project));
        if (filtered.length === 0) {
          return (
            <div style={{ ...card, padding: '40px', textAlign: 'center', color: C.textMuted }}>
              {myJournal.length === 0
                ? 'Истории работ пока нет. Введите работу на странице «Работы» — после подтверждения прорабом она появится здесь.'
                : 'По запросу ничего не найдено'}
            </div>
          );
        }

        const byDate = {};
        filtered.forEach((work) => {
          const date = String(work.date || work.confirmedAt || '').split('T')[0] || 'Без даты';
          if (!byDate[date]) byDate[date] = { works: [], total: 0, confirmedTotal: 0, pendingTotal: 0 };
          byDate[date].works.push(work);
          const amount = workAmount(work);
          if (workStatus(work) === 'Подтверждено') {
            byDate[date].confirmedTotal += amount;
            byDate[date].total += amount;
          } else if (workStatus(work) !== 'Отклонено') {
            byDate[date].pendingTotal += amount;
            byDate[date].total += amount;
          }
        });

        const dates = Object.keys(byDate).sort((a, b) => b.localeCompare(a));
        const paidWorkJournalIds = new Set(
          (piecework || [])
            .filter((pw) => Number(pw.staffId) === user.id && pw.workJournalId)
            .map((pw) => Number(pw.workJournalId))
        );

        return dates.map((date) => {
          const group = byDate[date];
          const isOpen = expandedProject === date;
          const byProject = {};
          group.works.forEach((work) => {
            const projectName = work.project || 'Без объекта';
            if (!byProject[projectName]) byProject[projectName] = [];
            byProject[projectName].push(work);
          });
          const projectNames = Object.keys(byProject).sort();

          return (
            <div key={date} style={{ ...card, marginBottom: '10px' }}>
              <div
                style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                onClick={() => setExpandedProject(isOpen ? null : date)}
              >
                <div>
                  <b style={{ color: C.text, fontSize: '14px' }}>📅 {date}</b>
                  <p style={{ color: C.textSec, margin: '3px 0', fontSize: '12px' }}>
                    {group.works.length + ' работ · ' + projectNames.length + (projectNames.length === 1 ? ' объект' : ' объекта/объектов')}
                  </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ textAlign: 'right' }}>
                    <b style={{ color: group.confirmedTotal > 0 ? C.success : C.warning, fontSize: '15px' }}>{Math.round(group.total).toLocaleString('ru-RU') + ' ₽'}</b>
                    <p style={{ color: C.textSec, margin: '2px 0 0', fontSize: '10px' }}>
                      {group.pendingTotal > 0 && group.confirmedTotal > 0
                        ? 'принято + проверка'
                        : group.pendingTotal > 0
                          ? 'к проверке'
                          : 'принято'}
                    </p>
                  </div>
                  {isOpen ? <ChevronUp size={16} color={C.textMuted} /> : <ChevronDown size={16} color={C.textMuted} />}
                </div>
              </div>

              {isOpen && (
                <div style={{ borderTop: '1.5px solid ' + C.border }}>
                  {projectNames.map((projectName) => (
                    <div key={projectName} style={{ padding: '10px 16px', borderBottom: '1px solid ' + C.border }}>
                      <b style={{ color: C.accent, fontSize: '12px', display: 'block', marginBottom: '6px' }}>🏗 {projectName}</b>
                      {byProject[projectName].map((work) => {
                        const status = workStatus(work);
                        const statusColor = status === 'Подтверждено' ? C.success : status === 'Отклонено' ? C.danger : C.warning;
                        const statusBackground = status === 'Подтверждено' ? C.successLight : status === 'Отклонено' ? C.dangerLight : C.warningLight;
                        const statusIcon = status === 'Подтверждено' ? '✅' : status === 'Отклонено' ? '❌' : '⏳';
                        const isPaid = paidWorkJournalIds.has(Number(work.id));
                        const amount = workAmount(work);

                        return (
                          <div key={work.id} style={{ padding: '8px 0', borderBottom: '1px solid ' + C.border, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px' }}>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <b style={{ fontSize: '13px', color: C.text, display: 'block' }}>{work.description}</b>
                              <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>{fmtMeasure(work.quantity, work.unit)}</p>
                              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '3px' }}>
                                <span style={{ padding: '2px 8px', borderRadius: '8px', fontSize: '10px', fontWeight: '600', backgroundColor: statusBackground, color: statusColor }}>
                                  {statusIcon + ' ' + status}
                                </span>
                                {status === 'Подтверждено' && (
                                  isPaid ? (
                                    <span style={{ padding: '2px 8px', borderRadius: '8px', fontSize: '10px', fontWeight: '600', backgroundColor: C.successLight, color: C.success }}>
                                      💰 Зачислено в зарплату
                                    </span>
                                  ) : (
                                    <span style={{ padding: '2px 8px', borderRadius: '8px', fontSize: '10px', fontWeight: '600', backgroundColor: C.warningLight, color: C.warning }}>
                                      ⏳ Ждёт зарплаты
                                    </span>
                                  )
                                )}
                              </div>
                              {work.comment && status === 'Отклонено' && <p style={{ color: C.danger, fontSize: '10px', margin: '4px 0 0' }}>Причина: {work.comment}</p>}
                            </div>
                            <div style={{ textAlign: 'right', flexShrink: 0 }}>
                              <b style={{ color: status === 'Подтверждено' ? C.success : status === 'Отклонено' ? C.textMuted : C.warning, fontSize: '13px' }}>
                                {Math.round(amount).toLocaleString('ru-RU') + ' ₽'}
                              </b>
                              {work.photoUrl && (
                                <button onClick={() => setShowPhotoModal(fileSrc(work.photoUrl))} style={{ ...btnG, padding: '2px 6px', fontSize: '10px', marginLeft: '4px', marginTop: '2px' }}>
                                  📷
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        });
      })()}
    </div>
  );
}
