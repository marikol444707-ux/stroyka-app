import React from 'react';
import { API } from '../api';

export default function ProjectHiddenWorksActsPanel({
  projectName,
  hiddenActs = [],
  setEditingAct,
  setHiddenActs,
  showPreview,
  buildHiddenActContent,
  showDelete = false,
  C,
  card,
  tbl,
  tblH,
  tblC,
  btnB,
  btnG,
  btnR,
}) {
  const actsHere = hiddenActs.filter(act => act.projectName === projectName);

  const deleteAct = async (act) => {
    if (!window.confirm('Удалить акт ' + act.actNumber + '?')) return;
    await fetch(API + '/hidden-works-acts/' + act.id, {method: 'DELETE'});
    setHiddenActs(prev => prev.filter(item => item.id !== act.id));
  };

  return (
    <div>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', flexWrap: 'wrap', gap: '10px'}}>
        <b style={{color: C.text, fontSize: '15px', fontWeight: '700'}}>АОСР к журналу работ</b>
        <span style={{fontSize: '11px', color: C.textMuted}}>Печатные формы по позициям сметы, отмеченным 🔒</span>
      </div>

      {actsHere.length === 0 ? (
        <div style={{...card, padding: '22px', textAlign: 'center', color: C.textMuted}}>
          <p style={{margin: '0 0 8px', fontWeight: '600'}}>Печатных форм АОСР пока нет</p>
          <p style={{fontSize: '12px', margin: 0, lineHeight: 1.6}}>
            Отметьте в смете позиции 🔒 и заполните «Сделано» — запись появится в журнале работ, а форма АОСР создастся автоматически.
          </p>
        </div>
      ) : (
        <div>
          <p style={{fontSize: '12px', color: C.textSec, margin: '0 0 10px'}}>
            Найдено форм: {actsHere.length}. Используйте строку журнала работ или кнопку печати для подготовки документа.
          </p>
          <div style={{...card, padding: 0, overflow: 'auto'}}>
            <table style={tbl}>
              <thead>
                <tr>
                  <th style={tblH}>№ акта</th>
                  <th style={tblH}>Раздел</th>
                  <th style={tblH}>Работа</th>
                  <th style={tblH}>Бригада</th>
                  <th style={tblH}>Объём</th>
                  <th style={tblH}>Дата</th>
                  <th style={tblH}>Статус</th>
                  <th style={tblH}></th>
                </tr>
              </thead>
              <tbody>
                {actsHere.map(act => (
                  <tr key={act.id} style={{cursor: 'pointer'}} onClick={() => setEditingAct(act)}>
                    <td style={tblC}><b style={{color: C.accent}}>{act.actNumber}</b></td>
                    <td style={tblC}>{act.sectionName || '—'}</td>
                    <td style={{...tblC, maxWidth: '280px', whiteSpace: 'normal'}}>{act.workName}</td>
                    <td style={tblC}>{act.brigade || '—'}</td>
                    <td style={tblC}>{act.quantity + ' ' + (act.unit || '')}</td>
                    <td style={tblC}>{act.workDate || '—'}</td>
                    <td style={tblC}>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: '10px',
                        fontSize: '11px',
                        fontWeight: '600',
                        backgroundColor: act.status === 'Подписан' ? C.successLight : C.warningLight,
                        color: act.status === 'Подписан' ? C.success : C.warning,
                      }}>
                        {act.status || 'Черновик'}
                      </span>
                    </td>
                    <td style={tblC} onClick={event => event.stopPropagation()}>
                      <div style={{display: 'flex', gap: '4px'}}>
                        <button onClick={() => setEditingAct(act)} title="Открыть карточку" style={{...btnB, padding: '3px 7px'}}>✏️</button>
                        <button onClick={() => showPreview(buildHiddenActContent(act), 'АОСР № ' + act.actNumber)} title="Печать по СНиП" style={{...btnG, padding: '3px 7px'}}>🖨️</button>
                        {showDelete && (
                          <button onClick={() => deleteAct(act)} title="Удалить" style={{...btnR, padding: '3px 7px'}}>🗑️</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
