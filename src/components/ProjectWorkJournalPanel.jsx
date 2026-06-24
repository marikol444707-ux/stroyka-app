import React from 'react';
import { Check, FileText, ScrollText, Search, X } from 'lucide-react';

export default function ProjectWorkJournalPanel({
  project,
  workJournal = [],
  workJournalPage = {},
  loadWorkJournalPage,
  weatherLog = [],
  listSearch,
  setListSearch,
  matchSearch,
  setShowJournalTableModal,
  showPreview,
  buildJPRContent,
  showKS2,
  setEditingJournal,
  getActStatusForJournal,
  setEditingAct,
  openConfirmModal,
  setRejectingEntry,
  canConfirm = false,
  showCustomerTotals = false,
  fileSrc,
  setShowPhotoModal,
  C,
  inp,
  btnB,
  btnG,
  btnGr,
  btnR,
  badge,
}) {
  const projectName = project.name;
  const [dateFrom, setDateFrom] = React.useState('');
  const [dateTo, setDateTo] = React.useState('');
  const workExecutionTotal = (work) => Number(work?.executionTotal ?? work?.execution_total ?? 0);
  const workCustomerTotal = (work) => Number(work?.customerTotal ?? work?.customer_total ?? work?.total ?? 0);
  const projectWorks = workJournal.filter(item => item.project === projectName);
  const unexpectedWorks = projectWorks.filter(item => item.unexpectedWorkId);
  const unexpectedTotal = unexpectedWorks.reduce((sum, item) => sum + workExecutionTotal(item), 0);
  const searchValue = String(listSearch || '').trim();
  const dateMatches = (item) => {
    const value = String(item.date || '').slice(0, 10);
    if (dateFrom && value < dateFrom) return false;
    if (dateTo && value > dateTo) return false;
    return true;
  };
  const filteredWorks = projectWorks.filter(item => (
    dateMatches(item) && matchSearch(searchValue, item.description, item.masterName || item.master_name, item.roomName, item.sectionName, item.workPackage, item.status)
  ));
  const queryMatches = workJournalPage.projectName === projectName
    && (workJournalPage.search || '') === searchValue
    && (workJournalPage.dateFrom || '') === dateFrom
    && (workJournalPage.dateTo || '') === dateTo;
  React.useEffect(() => {
    if (typeof loadWorkJournalPage !== 'function') return undefined;
    const timer = setTimeout(() => {
      loadWorkJournalPage({projectName, search: searchValue, dateFrom, dateTo, offset: 0});
    }, searchValue || dateFrom || dateTo ? 300 : 0);
    return () => clearTimeout(timer);
  }, [projectName, searchValue, dateFrom, dateTo, loadWorkJournalPage]);

  const groupedByDate = {};
  filteredWorks.forEach(item => {
    if (!groupedByDate[item.date]) groupedByDate[item.date] = {};
    if (!groupedByDate[item.date][item.masterName]) groupedByDate[item.date][item.masterName] = [];
    groupedByDate[item.date][item.masterName].push(item);
  });

  return (
    <div>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', flexWrap: 'wrap', gap: '8px'}}>
        <b style={{color: C.text}}>Журнал производства работ</b>
        <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap'}}>
          <button onClick={() => setShowJournalTableModal(projectName)} style={btnB}>
            <FileText size={14}/>📋 Таблица КС-6а
          </button>
          <button onClick={() => showPreview(buildJPRContent(projectName), 'ЖПР — ' + projectName)} style={btnG}>
            <ScrollText size={14}/>ЖПР
          </button>
          <button onClick={() => showKS2(project)} style={btnG}>
            <FileText size={14}/>КС-2
          </button>
        </div>
      </div>

      {unexpectedWorks.length > 0 && (
        <div style={{marginBottom: '12px', padding: '10px 12px', backgroundColor: '#fef3c7', border: '1.5px solid #fbbf24', borderRadius: '10px', fontSize: '13px', color: '#78350f'}}>
          🆕 <b>Работы вне сметы:</b> {unexpectedWorks.length} позиц. на <b>{Math.round(unexpectedTotal).toLocaleString('ru-RU') + ' ₽'}</b> (оформлены доп.соглашениями) — подсвечены жёлтым в списке ниже
        </div>
      )}

      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(150px,1fr))',gap:'8px',alignItems:'center',marginBottom:'10px'}}>
        <div style={{position: 'relative', minWidth: 0}}>
          <Search size={14} style={{position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: C.textMuted}}/>
          <input
            placeholder="🔍 Поиск по работам, мастерам, помещению"
            value={listSearch}
            onChange={event => setListSearch(event.target.value)}
            style={{...inp, marginBottom: 0, paddingLeft: '32px', fontSize: '12px', padding: '6px 8px 6px 32px'}}
          />
        </div>
        <input type="date" value={dateFrom} onChange={event => setDateFrom(event.target.value)} style={{...inp,marginBottom:0,fontSize:'12px',padding:'6px 8px'}} />
        <input type="date" value={dateTo} onChange={event => setDateTo(event.target.value)} style={{...inp,marginBottom:0,fontSize:'12px',padding:'6px 8px'}} />
        {queryMatches && (workJournalPage.loading || workJournalPage.error) && (
          <p style={{gridColumn:'1 / -1',color:workJournalPage.error ? C.danger : C.textMuted,fontSize:'11px',margin:'-2px 0 0'}}>
            {workJournalPage.error || 'Ищу записи ЖПР на сервере...'}
          </p>
        )}
      </div>

      {Object.keys(groupedByDate).sort().reverse().map(date => {
        const weather = weatherLog.find(item => item.projectName === projectName && item.date === date);
        return (
          <div key={date} style={{marginBottom: '16px'}}>
            <div style={{display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px'}}>
              <b style={{color: C.text, fontSize: '13px'}}>{date}</b>
              {weather && <span style={{fontSize: '12px', color: C.info}}>{'🌤️ ' + weather.condition + ' ' + weather.temperature + '°C'}</span>}
            </div>

            {Object.keys(groupedByDate[date]).map(masterName => (
              <div key={masterName} style={{marginBottom: '8px'}}>
                <p style={{color: C.accent, fontSize: '12px', fontWeight: '600', margin: '0 0 6px'}}>{'👷 ' + masterName}</p>
                {groupedByDate[date][masterName].map(item => {
                  const executionTotal = workExecutionTotal(item);
                  const customerTotal = workCustomerTotal(item);
                  const showCustomerTotal = showCustomerTotals && Math.abs(customerTotal - executionTotal) > 1;
                  return (
                  <div
                    key={item.id}
                    onClick={() => setEditingJournal(item)}
                    style={{
                      padding: '8px 10px',
                      backgroundColor: item.unexpectedWorkId ? '#fef3c7' : C.bg,
                      borderRadius: '8px',
                      marginBottom: '4px',
                      border: '1.5px solid ' + (item.unexpectedWorkId ? '#fbbf24' : C.border),
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      cursor: 'pointer',
                    }}
                  >
                    <div>
                      <b style={{fontSize: '12px', color: C.text}}>
                        {item.description}
                        {item.unexpectedWorkId ? <span title="Непредвиденная работа (доп.соглашение)" style={{marginLeft: '4px', color: C.warning}}>🆕</span> : null}
                        {item.hiddenWork ? (() => {
                          const status = getActStatusForJournal(item);
                          return (
                            <span
                              title={status && status.act ? 'Открыть печатную форму АОСР' : 'Позиция актируется в АОСР'}
                              style={{marginLeft: '4px', cursor: status && status.act ? 'pointer' : 'default'}}
                              onClick={event => {
                                if (status && status.act) {
                                  event.stopPropagation();
                                  setEditingAct(status.act);
                                }
                              }}
                            >
                              🔒{status ? status.icon : ''}
                            </span>
                          );
                        })() : null}
                      </b>
                      <p style={{color: C.textSec, margin: '1px 0', fontSize: '11px'}}>
                        {item.quantity + ' ' + item.unit + (item.roomName ? ' · ' + item.roomName : '')}
                      </p>
                    </div>

                    <div style={{display: 'flex', alignItems: 'center', gap: '6px'}}>
                      <div style={{textAlign: 'right'}}>
                        <b style={{display: 'block', color: C.success, fontSize: '12px'}}>{executionTotal.toLocaleString('ru-RU') + ' ₽'}</b>
                        {showCustomerTotal && <span style={{display: 'block', color: C.textMuted, fontSize: '10px'}}>заказч. {customerTotal.toLocaleString('ru-RU') + ' ₽'}</span>}
                      </div>
                      {canConfirm && item.status === 'На проверке' && (
                        <>
                          <button onClick={event => { event.stopPropagation(); openConfirmModal(item); }} style={{...btnGr, padding: '3px 8px', fontSize: '11px'}} title="Принять (можно пересчитать)">
                            <Check size={11}/>
                          </button>
                          <button onClick={event => { event.stopPropagation(); setRejectingEntry(item); }} style={{...btnR, padding: '3px 8px', fontSize: '11px'}} title="Отклонить">
                            <X size={11}/>
                          </button>
                        </>
                      )}
                      {item.status === 'Подтверждено' && <span style={badge(C.success, C.successLight, C.successBorder)}>✅</span>}
                      {item.status === 'Отклонено' && <span style={badge(C.danger, C.dangerLight, C.dangerBorder)}>❌</span>}
                      {item.photoUrl && (
                        <img
                          src={fileSrc(item.photoUrl)}
                          alt=""
                          onClick={event => { event.stopPropagation(); setShowPhotoModal(fileSrc(item.photoUrl)); }}
                          style={{width: '32px', height: '32px', borderRadius: '6px', objectFit: 'cover', cursor: 'pointer'}}
                        />
                      )}
                    </div>
                  </div>
                  );
                })}
              </div>
            ))}
          </div>
        );
      })}

      {projectWorks.length === 0 && (
        <p style={{color: C.textMuted, textAlign: 'center', padding: '20px'}}>Работ нет</p>
      )}
      {typeof loadWorkJournalPage === 'function' && queryMatches && workJournalPage.hasMore && (
        <button
          type="button"
          onClick={() => loadWorkJournalPage({projectName, search: searchValue, dateFrom, dateTo, offset: filteredWorks.length})}
          disabled={workJournalPage.loading}
          style={{...btnB, width:'100%', justifyContent:'center', marginTop:'12px', opacity:workJournalPage.loading ? 0.65 : 1}}
        >
          {workJournalPage.loading ? 'Загружаю ЖПР...' : 'Загрузить ещё записи ЖПР'}
        </button>
      )}
      {queryMatches && workJournalPage.error && (
        <p style={{color: C.danger, fontSize:'12px', margin:'8px 0 0'}}>{workJournalPage.error}</p>
      )}
    </div>
  );
}
