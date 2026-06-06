import React from 'react';
import { Eye, X } from 'lucide-react';

export default function ProjectWorkJournalTableModal({
  projectName,
  workJournal = [],
  journalFilter,
  setJournalFilter,
  setShowJournalTableModal,
  setEditingJournal,
  getActStatusForJournal,
  setEditingAct,
  showPreview,
  buildWorkJournalContent,
  fmtMeasure,
  C,
  card,
  inp,
  tbl,
  tblH,
  tblC,
  btnB,
  btnG,
}) {
  if (!projectName) return null;

  const journalHere = workJournal.filter(item => item.project === projectName);
  let filtered = journalHere;
  if (journalFilter.from) filtered = filtered.filter(item => (item.date || '') >= journalFilter.from);
  if (journalFilter.to) filtered = filtered.filter(item => (item.date || '') <= journalFilter.to);
  if (journalFilter.masterName) filtered = filtered.filter(item => (item.masterName || '') === journalFilter.masterName);
  if (journalFilter.sectionName) filtered = filtered.filter(item => (item.sectionName || '') === journalFilter.sectionName);
  if (journalFilter.status) filtered = filtered.filter(item => item.status === journalFilter.status);

  const sections = [...new Set(journalHere.map(item => item.sectionName).filter(Boolean))];
  const masters = [...new Set(journalHere.map(item => item.masterName).filter(Boolean))];
  const sumFiltered = filtered.reduce((sum, item) => sum + Number(item.total || 0), 0);
  const countDraft = filtered.filter(item => item.status === 'На проверке').length;
  const countConfirmed = filtered.filter(item => item.status === 'Подтверждено').length;

  return (
    <div onClick={() => setShowJournalTableModal(null)} style={{position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.55)', zIndex: 1600, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'}}>
      <div onClick={event => event.stopPropagation()} style={{...card, padding: 0, width: 'min(1100px,100%)', maxHeight: '92vh', display: 'flex', flexDirection: 'column', overflow: 'hidden'}}>
        <div style={{padding: '16px 20px', borderBottom: '1.5px solid ' + C.border, backgroundColor: C.bg, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px'}}>
          <div>
            <b style={{color: C.text, fontSize: '16px', display: 'block'}}>📋 Журнал работ — Таблица КС-6а</b>
            <span style={{fontSize: '12px', color: C.textSec}}>{projectName + ' · РД-11-05-2007 · СП 48.13330.2019'}</span>
          </div>
          <button onClick={() => setShowJournalTableModal(null)} style={{...btnG, padding: '5px 10px'}}>
            <X size={14}/>
          </button>
        </div>

        <div style={{flex: 1, overflowY: 'auto', padding: '18px 20px'}}>
          {journalHere.length === 0 ? (
            <div style={{...card, padding: '30px', textAlign: 'center', color: C.textMuted}}>Записей в журнале пока нет</div>
          ) : (
            <div>
              <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(110px,1fr))', gap: '8px', marginBottom: '12px'}}>
                <input type="date" value={journalFilter.from} onChange={event => setJournalFilter({...journalFilter, from: event.target.value})} title="Период с" style={{...inp, marginBottom: 0, fontSize: '11px'}}/>
                <input type="date" value={journalFilter.to} onChange={event => setJournalFilter({...journalFilter, to: event.target.value})} title="Период по" style={{...inp, marginBottom: 0, fontSize: '11px'}}/>
                <select value={journalFilter.sectionName} onChange={event => setJournalFilter({...journalFilter, sectionName: event.target.value})} style={{...inp, marginBottom: 0, fontSize: '11px'}}>
                  <option value="">Все разделы</option>
                  {sections.map(section => <option key={section} value={section}>{section}</option>)}
                </select>
                <select value={journalFilter.masterName} onChange={event => setJournalFilter({...journalFilter, masterName: event.target.value})} style={{...inp, marginBottom: 0, fontSize: '11px'}}>
                  <option value="">Все исполнители</option>
                  {masters.map(master => <option key={master} value={master}>{master}</option>)}
                </select>
                <select value={journalFilter.status} onChange={event => setJournalFilter({...journalFilter, status: event.target.value})} style={{...inp, marginBottom: 0, fontSize: '11px'}}>
                  <option value="">Все статусы</option>
                  <option>На проверке</option>
                  <option>Подтверждено</option>
                  <option>Отклонено</option>
                </select>
                <button onClick={() => showPreview(buildWorkJournalContent(filtered, projectName, journalFilter.from, journalFilter.to), 'КС-6а — ' + projectName)} style={{...btnB, fontSize: '11px', padding: '7px 10px'}}>
                  <Eye size={12}/>🖨 Печать КС-6а
                </button>
              </div>

              <div style={{display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '10px', marginBottom: '14px'}}>
                <div style={{...card, padding: '12px', backgroundColor: C.bg}}>
                  <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 4px'}}>Записей</p>
                  <b style={{color: C.text, fontSize: '16px'}}>{filtered.length}</b>
                </div>
                <div style={{...card, padding: '12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder}}>
                  <p style={{color: C.warning, fontSize: '11px', margin: '0 0 4px'}}>На проверке</p>
                  <b style={{color: C.warning, fontSize: '16px'}}>{countDraft}</b>
                </div>
                <div style={{...card, padding: '12px', backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder}}>
                  <p style={{color: C.success, fontSize: '11px', margin: '0 0 4px'}}>Подтверждено</p>
                  <b style={{color: C.success, fontSize: '16px'}}>{countConfirmed}</b>
                </div>
              </div>

              <div style={{...card, padding: 0, overflow: 'auto'}}>
                <table style={tbl}>
                  <thead>
                    <tr>
                      <th style={tblH}>Дата</th>
                      <th style={tblH}>Тип</th>
                      <th style={tblH}>Раздел</th>
                      <th style={tblH}>Работа</th>
                      <th style={tblH}>Объём</th>
                      <th style={tblH}>Исполнитель</th>
                      <th style={tblH}>ИТР</th>
                      <th style={tblH}>Погода</th>
                      <th style={tblH}>Качество</th>
                      <th style={tblH}>Статус</th>
                      <th style={tblH}>Сумма</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(item => (
                      <tr key={item.id} style={{cursor: 'pointer', backgroundColor: item.unexpectedWorkId ? '#fef3c7' : undefined}} onClick={() => { setEditingJournal(item); setShowJournalTableModal(null); }}>
                        <td style={tblC}>{item.date || '—'}</td>
                        <td style={tblC}>
                          {item.unexpectedWorkId ? (
                            <span style={{padding: '2px 6px', borderRadius: '8px', fontSize: '10px', fontWeight: '700', backgroundColor: '#fbbf24', color: '#78350f'}}>🆕 вне сметы</span>
                          ) : (
                            <span style={{padding: '2px 6px', borderRadius: '8px', fontSize: '10px', fontWeight: '600', backgroundColor: C.bg, color: C.textSec}}>по смете</span>
                          )}
                        </td>
                        <td style={tblC}>{item.sectionName || '—'}</td>
                        <td style={{...tblC, maxWidth: '260px', whiteSpace: 'normal'}}>
                          {item.description}
                          {item.hiddenWork ? (() => {
                            const status = getActStatusForJournal({...item, project: item.project || projectName});
                            return (
                              <span
                                title={status && status.act ? 'Открыть печатную форму АОСР' : 'Позиция актируется в АОСР'}
                                style={{marginLeft: '4px', cursor: status && status.act ? 'pointer' : 'default'}}
                                onClick={event => {
                                  if (status && status.act) {
                                    event.stopPropagation();
                                    setEditingAct(status.act);
                                    setShowJournalTableModal(null);
                                  }
                                }}
                              >
                                🔒{status ? status.icon : ''}
                              </span>
                            );
                          })() : null}
                          {item.aiFilled ? <span title="Заполнено AI" style={{marginLeft: '4px'}}>🤖</span> : null}
                        </td>
                        <td style={tblC}>{fmtMeasure(item.quantity, item.unit)}</td>
                        <td style={tblC}>{item.masterName || '—'}</td>
                        <td style={tblC}>{item.responsibleItr || '—'}</td>
                        <td style={tblC}>{item.weather || '—'}</td>
                        <td style={tblC}>{item.qualityStatus || '—'}</td>
                        <td style={tblC}>
                          <span style={{
                            padding: '2px 8px',
                            borderRadius: '10px',
                            fontSize: '11px',
                            fontWeight: '600',
                            backgroundColor: item.status === 'Подтверждено' ? C.successLight : item.status === 'Отклонено' ? C.dangerLight : C.warningLight,
                            color: item.status === 'Подтверждено' ? C.success : item.status === 'Отклонено' ? C.danger : C.warning,
                          }}>
                            {item.status || '—'}
                          </span>
                        </td>
                        <td style={tblC}>{Number(item.total || 0).toLocaleString('ru-RU') + ' ₽'}</td>
                      </tr>
                    ))}
                    {filtered.length === 0 && (
                      <tr>
                        <td colSpan={11} style={{...tblC, textAlign: 'center', color: C.textMuted}}>По выбранным фильтрам записей нет</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div style={{marginTop: '12px', padding: '12px', backgroundColor: C.accentLight, border: '1.5px solid ' + C.accentBorder, borderRadius: '10px', textAlign: 'right'}}>
                <span style={{color: C.textSec, fontSize: '12px', marginRight: '10px'}}>Сумма по фильтру:</span>
                <b style={{color: C.accent, fontSize: '15px'}}>{sumFiltered.toLocaleString('ru-RU') + ' ₽'}</b>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
