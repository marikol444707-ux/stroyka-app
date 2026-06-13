import React from 'react';
import {
  Check,
  ChevronDown,
  ChevronUp,
  DollarSign,
  Eye,
  Plus,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import { API } from '../api';

export default function AccountingActsPanel({
  C,
  card,
  inp,
  btnO,
  btnG,
  btnB,
  btnR,
  badge,
  listSearch,
  setListSearch,
  matchSearch,
  workJournal,
  unexpectedWorksList,
  isApprovedEstimateChangeStatus,
  expandedProject,
  setExpandedProject,
  expandedActDate,
  setExpandedActDate,
  fmtMeasure,
  showForm,
  setShowForm,
  isFinanceRole,
  newAct,
  setNewAct,
  masterProfiles,
  staff,
  projects,
  createInterimAct,
  interimActs,
  showPreview,
  buildActContent,
  fileSrc,
  uploadPhoto,
  refreshData,
  setShowPayActModal,
  deleteInterimAct,
  brigadeContracts,
  buildBrigadeActContent,
}) {
  const filteredInterimActs = (interimActs || []).filter(act => matchSearch(listSearch, act.masterName, act.project));
  const workPayTotal = (work) => Number(work.executionTotal ?? work.execution_total ?? work.total ?? 0);

  const allWorks = [
    ...((workJournal || []).filter(work => work.status === 'Подтверждено').map(work => ({ ...work, _kind: 'journal' }))),
    ...((unexpectedWorksList || [])
      .filter(work => isApprovedEstimateChangeStatus(work.status))
      .map(work => ({
        id: 'unx-' + work.id,
        description: work.description,
        project: work.projectName,
        masterName: work.addedBy,
        total: work.total,
        quantity: work.deltaQuantity || work.quantity,
        unit: work.unit,
        date: work.approvedAt || work.createdAt,
        _kind: 'estimate_change',
      }))),
  ].filter(work => matchSearch(listSearch, work.description, work.masterName, work.project));

  const worksByProject = allWorks.reduce((acc, work) => {
    const projectName = work.project || 'Без объекта';
    if (!acc[projectName]) acc[projectName] = { works: [], total: 0, estimateChangesTotal: 0 };
    acc[projectName].works.push(work);
    acc[projectName].total += work._kind === 'journal' ? workPayTotal(work) : Number(work.total || 0);
    if (work._kind === 'estimate_change') acc[projectName].estimateChangesTotal += Number(work.total || 0);
    return acc;
  }, {});

  const brigadeContractsWithDone = (brigadeContracts || []).filter(contract => matchSearch(listSearch, contract.brigadeName, contract.projectName) && Number(contract.doneAmount || 0) > 0);
  const brigadeByProject = brigadeContractsWithDone.reduce((acc, contract) => {
    const projectName = contract.projectName || 'Без объекта';
    if (!acc[projectName]) acc[projectName] = [];
    acc[projectName].push(contract);
    return acc;
  }, {});

  return (
    <div>
      <div style={{ ...card, padding: '14px', marginBottom: '14px', backgroundColor: C.bg }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
          <b style={{ color: C.text, fontSize: '14px' }}>🏗 Производство работ по объектам</b>
          <span style={{ color: C.textSec, fontSize: '11px' }}>Открой объект → увидишь все акты по дням</span>
        </div>
        <div style={{ position: 'relative', marginBottom: '10px' }}>
          <Search size={13} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: C.textMuted }} />
          <input
            placeholder='🔍 Поиск работы, мастера, объекта'
            value={listSearch}
            onChange={event => setListSearch(event.target.value)}
            style={{ ...inp, marginBottom: 0, paddingLeft: '30px', fontSize: '12px', padding: '6px 8px 6px 30px' }}
          />
        </div>
        {allWorks.length === 0 ? (
          <p style={{ color: C.textMuted, textAlign: 'center', padding: '20px', fontSize: '12px' }}>
            Работ ещё нет. После подтверждения мастером и приёма прорабом — появятся здесь.
          </p>
        ) : (
          Object.keys(worksByProject).sort().map(projectName => {
            const group = worksByProject[projectName];
            const isProjectOpen = expandedProject === 'act-' + projectName;
            const worksByDate = group.works.reduce((acc, work) => {
              const dateKey = String(work.date || work.confirmedAt || '').split('T')[0] || 'Без даты';
              if (!acc[dateKey]) acc[dateKey] = [];
              acc[dateKey].push(work);
              return acc;
            }, {});
            const dates = Object.keys(worksByDate).sort((a, b) => b.localeCompare(a));
            return (
              <div key={projectName} style={{ ...card, marginBottom: '8px', backgroundColor: C.bgWhite, borderLeft: '3px solid ' + C.accent }}>
                <div
                  style={{ padding: '12px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', flexWrap: 'wrap', gap: '8px' }}
                  onClick={() => setExpandedProject(isProjectOpen ? null : 'act-' + projectName)}
                >
                  <div>
                    <b style={{ color: C.text, fontSize: '14px' }}>🏗 {projectName}</b>
                    <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>
                      {group.works.length + ' работ · ' + dates.length + ' дн.'}
                      {group.estimateChangesTotal > 0 ? ' · 🆕 ' + Math.round(group.estimateChangesTotal).toLocaleString('ru-RU') + ' ₽ непредв.' : ''}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <b style={{ color: C.success, fontSize: '15px' }}>{Math.round(group.total).toLocaleString('ru-RU') + ' ₽'}</b>
                    {isProjectOpen ? <ChevronUp size={14} color={C.textMuted} /> : <ChevronDown size={14} color={C.textMuted} />}
                  </div>
                </div>
                {isProjectOpen && (
                  <div style={{ borderTop: '1px solid ' + C.border }}>
                    {dates.map(date => {
                      const dayWorks = worksByDate[date];
                      const daySum = dayWorks.reduce((sum, work) => sum + (work._kind === 'journal' ? workPayTotal(work) : Number(work.total || 0)), 0);
                      const isDateOpen = expandedActDate === projectName + '_' + date;
                      const worksByMaster = dayWorks.reduce((acc, work) => {
                        const masterName = work.masterName || '—';
                        if (!acc[masterName]) acc[masterName] = [];
                        acc[masterName].push(work);
                        return acc;
                      }, {});
                      const masters = Object.keys(worksByMaster).sort();
                      return (
                        <div key={date} style={{ borderBottom: '1px solid ' + C.border }}>
                          <div
                            style={{ padding: '8px 14px 8px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                            onClick={() => setExpandedActDate(isDateOpen ? null : projectName + '_' + date)}
                          >
                            <span style={{ color: C.text, fontSize: '12px', fontWeight: '600' }}>📅 {date}</span>
                            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                              <span style={{ color: C.textSec, fontSize: '11px' }}>{dayWorks.length + ' · ' + masters.length + ' маст.'}</span>
                              <b style={{ color: C.success, fontSize: '12px' }}>{Math.round(daySum).toLocaleString('ru-RU') + ' ₽'}</b>
                              {isDateOpen ? <ChevronUp size={12} color={C.textMuted} /> : <ChevronDown size={12} color={C.textMuted} />}
                            </div>
                          </div>
                          {isDateOpen && (
                            <div style={{ padding: '0 14px 8px 34px', backgroundColor: C.bg }}>
                              {masters.map(masterName => (
                                <div key={masterName} style={{ marginBottom: '4px' }}>
                                  <span style={{ color: C.accent, fontSize: '11px', fontWeight: '700' }}>👷 {masterName}</span>
                                  {worksByMaster[masterName].map(work => (
                                    <div
                                      key={work.id}
                                      style={{ padding: '4px 0 4px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', fontSize: '11px', borderBottom: '1px dashed ' + C.border }}
                                    >
                                      <div style={{ flex: 1, minWidth: 0 }}>
                                        <span style={{ color: C.text }}>{work.description}</span>
                                        {work._kind === 'estimate_change' && <span style={{ marginLeft: '4px', color: C.warning, fontSize: '10px' }}>🆕 непредв.</span>}
                                        <span style={{ color: C.textMuted, marginLeft: '4px' }}>{fmtMeasure(work.quantity, work.unit)}</span>
                                      </div>
                                      <b style={{ color: C.text, whiteSpace: 'nowrap' }}>{Math.round(work._kind === 'journal' ? workPayTotal(work) : Number(work.total || 0)).toLocaleString('ru-RU') + ' ₽'}</b>
                                    </div>
                                  ))}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
        <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>📄 Акты к оплате</b>
        {isFinanceRole() && (
          <button onClick={() => setShowForm(!showForm)} style={btnO}>
            <Plus size={14} />
            Сформировать акт
          </button>
        )}
      </div>
      {showForm && (
        <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <select
              value={newAct.masterId}
              onChange={event => {
                const profile = (masterProfiles || []).find(item => item.userId === Number(event.target.value));
                const staffRow = (staff || []).find(item => item.id === Number(event.target.value));
                setNewAct({
                  ...newAct,
                  masterId: event.target.value,
                  masterName: profile ? profile.fullName : (staffRow ? staffRow.name : ''),
                });
              }}
              style={{ ...inp, marginBottom: 0 }}
            >
              <option value="">Выберите исполнителя *</option>
              {[
                { label: '👷 Мастера и субподрядчики', roles: ['мастер', 'субподрядчик', 'бригадир'] },
                { label: '🏢 Юр.лица (ИП/ООО)', roles: ['организация', 'ип', 'ооо'] },
              ].map(group => {
                const items = (staff || []).filter(item => group.roles.includes(String(item.role || '').toLowerCase()));
                if (items.length === 0) return null;
                return (
                  <optgroup key={group.label} label={group.label}>
                    {items.map(item => (
                      <option key={item.id} value={item.id}>
                        {item.name + (item.specialization ? ' · ' + item.specialization : '')}
                      </option>
                    ))}
                  </optgroup>
                );
              })}
            </select>
            <select value={newAct.project} onChange={event => setNewAct({ ...newAct, project: event.target.value })} style={{ ...inp, marginBottom: 0 }}>
              <option value="">Объект *</option>
              {(projects || []).map(project => <option key={project.id} value={project.name}>{project.name}</option>)}
            </select>
            <input type="date" step="any" inputMode="decimal" placeholder="Период с *" value={newAct.periodStart} onChange={event => setNewAct({ ...newAct, periodStart: event.target.value })} style={{ ...inp, marginBottom: 0 }} />
            <input type="date" step="any" inputMode="decimal" placeholder="Период по *" value={newAct.periodEnd} onChange={event => setNewAct({ ...newAct, periodEnd: event.target.value })} style={{ ...inp, marginBottom: 0 }} />
          </div>
          <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <button onClick={createInterimAct} style={btnO}>
              <Check size={14} />
              Создать
            </button>
            <button onClick={() => setShowForm(false)} style={btnG}>
              <X size={14} />
              Отмена
            </button>
          </div>
        </div>
      )}
      {filteredInterimActs.map(act => {
        const paidAmount = Number(act.paidAmount || 0);
        const totalAmount = Number(act.totalAmount || 0);
        const remaining = totalAmount - paidAmount;
        return (
          <div key={act.id} style={{ ...card, padding: '14px', marginBottom: '8px', borderLeft: '3px solid ' + (act.status === 'Оплачен' ? C.success : remaining > 0 && paidAmount > 0 ? C.warning : C.textSec) }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <b style={{ color: C.text, fontSize: '13px' }}>{'Акт №' + act.id + ' · ' + act.masterName}</b>
                <p style={{ color: C.textSec, margin: '2px 0', fontSize: '12px' }}>{act.project + ' · ' + act.periodStart + ' — ' + act.periodEnd}</p>
                <div style={{ display: 'flex', gap: '12px', marginTop: '4px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '12px', color: C.text }}>{'Начислено: ' + totalAmount.toLocaleString() + ' ₽'}</span>
                  <span style={{ fontSize: '12px', color: C.success }}>{'Оплачено: ' + paidAmount.toLocaleString() + ' ₽'}</span>
                  {remaining > 0 && <span style={{ fontSize: '12px', color: C.danger, fontWeight: '700', padding: '2px 8px', borderRadius: '6px', backgroundColor: C.dangerLight }}>{'⚠️ Недоплата: ' + remaining.toLocaleString() + ' ₽'}</span>}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                <span style={badge(act.status === 'Оплачен' ? C.success : act.status === 'Частично оплачен' ? C.warning : C.textSec, act.status === 'Оплачен' ? C.successLight : act.status === 'Частично оплачен' ? C.warningLight : C.bgGray, act.status === 'Оплачен' ? C.successBorder : act.status === 'Частично оплачен' ? C.warningBorder : C.border)}>
                  {act.status || 'Не оплачен'}
                </span>
                <button onClick={() => showPreview(buildActContent(act), 'Акт')} style={btnB}>
                  <Eye size={13} />
                </button>
                {isFinanceRole() && (
                  act.scanUrl ? (
                    <a href={fileSrc(act.scanUrl)} target='_blank' rel='noreferrer' style={{ ...btnB, padding: '4px 8px', fontSize: '11px', textDecoration: 'none' }} title='Подписанный акт (скан)'>
                      📎
                    </a>
                  ) : (
                    <label style={{ ...btnG, padding: '4px 8px', fontSize: '11px', cursor: 'pointer', margin: 0 }} title='Загрузить скан подписанного акта'>
                      📎
                      <input
                        type='file'
                        style={{ display: 'none' }}
                        onChange={async event => {
                          const file = event.target.files[0];
                          if (!file) return;
                          const url = await uploadPhoto(file, { projectName: act.projectName || act.project, context: 'interim-acts' });
                          if (!url) return;
                          await fetch(API + '/interim-acts/' + act.id, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ scanUrl: url }),
                          });
                          await refreshData();
                        }}
                      />
                    </label>
                  )
                )}
                {isFinanceRole() && (
                  act.scanUrl ? (
                    <button onClick={() => setShowPayActModal(act)} style={btnO}>
                      <DollarSign size={13} />
                      Оплата
                    </button>
                  ) : (
                    <button onClick={() => window.alert('Оплата заблокирована: сначала загрузите скан подписанного бумажного акта (кнопка 📎).')} style={{ ...btnG, opacity: 0.6 }} title='Нет скана подписанного акта'>
                      <DollarSign size={13} />
                      Оплата 🔒
                    </button>
                  )
                )}
                <button onClick={() => deleteInterimAct(act.id)} style={{ ...btnR, padding: '4px 8px' }}>
                  <Trash2 size={11} />
                </button>
              </div>
            </div>
          </div>
        );
      })}
      {filteredInterimActs.length === 0 && (
        <p style={{ color: C.textMuted, textAlign: 'center', padding: '20px', fontSize: '12px' }}>
          Актов к оплате пока нет. Сформируйте акт за период по мастеру — стянутся подтверждённые работы.
        </p>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '18px 0 12px', flexWrap: 'wrap', gap: '8px' }}>
        <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>👷 Акты бригад (выполнение по смете)</b>
      </div>
      {brigadeContractsWithDone.length === 0 ? (
        <p style={{ color: C.textMuted, textAlign: 'center', padding: '20px', fontSize: '12px' }}>
          Выполненных работ по бригадам пока нет. Появятся, когда мастер отметит «Сделано» в смете объекта.
        </p>
      ) : (
        Object.keys(brigadeByProject).sort().map(projectName => (
          <div key={projectName} style={{ ...card, padding: '12px 14px', marginBottom: '8px' }}>
            <b style={{ color: C.text, fontSize: '13px', display: 'block', marginBottom: '8px' }}>🏗 {projectName}</b>
            {brigadeByProject[projectName].map(contract => {
              const due = Math.round(Number(contract.doneAmount || 0));
              const paid = Math.round(Number(contract.paidAmount || 0));
              const owe = Math.max(0, due - paid);
              return (
                <div key={contract.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', padding: '8px 0', borderBottom: '1px solid ' + C.border, flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <b style={{ fontSize: '12px', color: C.text }}>{contract.brigadeName}</b>
                    <span style={{ color: C.textSec, fontSize: '11px', marginLeft: '6px' }}>{contract.contractorType}</span>
                    <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginTop: '2px' }}>
                      <span style={{ fontSize: '11px', color: C.accent }}>{'К оплате: ' + due.toLocaleString('ru-RU') + ' ₽'}</span>
                      <span style={{ fontSize: '11px', color: C.success }}>{'Оплачено: ' + paid.toLocaleString('ru-RU') + ' ₽'}</span>
                      {owe > 0 && <span style={{ fontSize: '11px', color: C.danger, fontWeight: '700' }}>{'Остаток: ' + owe.toLocaleString('ru-RU') + ' ₽'}</span>}
                      {due > 0 && owe <= 0 && <span style={{ fontSize: '11px', color: C.success, fontWeight: '700' }}>✓ закрыто</span>}
                    </div>
                  </div>
                  <button onClick={() => showPreview(buildBrigadeActContent(contract), 'Акт бригады — ' + contract.brigadeName)} style={btnB}>
                    <Eye size={13} />
                    Акт
                  </button>
                </div>
              );
            })}
          </div>
        ))
      )}
    </div>
  );
}
