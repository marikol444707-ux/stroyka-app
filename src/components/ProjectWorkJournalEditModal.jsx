import React from 'react';
import { Bot, Check, Eye, X } from 'lucide-react';
import { API } from '../api';

export default function ProjectWorkJournalEditModal({
  journal,
  setEditingJournal,
  setWorkJournal,
  weatherLog = [],
  users = [],
  hiddenActs = [],
  setEditingAct,
  showPreview,
  buildWorkJournalContent,
  fmtMeasure,
  C,
  card,
  inp,
  btnB,
  btnG,
  btnO,
  aiNotice,
  aiNoticeIcon,
  aiNoticeText,
}) {
  if (!journal) return null;

  const updateJournal = (key, value) => setEditingJournal({...journal, [key]: value});
  const todayWeather = weatherLog.find(item => item.projectName === journal.project && item.date === journal.date);
  const prorabNames = users
    .filter(user => ['прораб', 'главный_инженер', 'зам_директора'].includes(user.role))
    .map(user => user.name)
    .filter(Boolean);
  const labelStyle = {fontSize: '11px', color: C.textSec, fontWeight: '600', marginBottom: '4px', display: 'block'};
  const sectionStyle = {marginBottom: '14px'};

  const fillByAI = async () => {
    setEditingJournal(prev => ({...prev, __aiLoading: true}));
    try {
      const res = await fetch(API + '/work-journal/' + journal.id + '/ai-prefill', {method: 'POST'});
      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.detail || ('HTTP ' + res.status));
      }
      const data = await res.json();
      setEditingJournal(prev => ({
        ...prev,
        normatives: data.normatives || prev.normatives,
        projectDocs: data.projectDocs || prev.projectDocs,
        comment: (prev.comment && prev.comment.trim()) ? prev.comment : (data.qualityNote || ''),
        aiFilled: true,
        __aiLoading: false,
      }));
      setWorkJournal(prev => prev.map(item => (
        item.id === journal.id
          ? {...item, normatives: data.normatives || item.normatives, projectDocs: data.projectDocs || item.projectDocs, aiFilled: true}
          : item
      )));
    } catch (error) {
      alert('Не получилось получить ответ от AI: ' + error.message);
      setEditingJournal(prev => ({...prev, __aiLoading: false}));
    }
  };

  const saveJournal = async () => {
    const body = {
      status: journal.status || 'На проверке',
      comment: journal.comment || '',
      responsibleItr: journal.responsibleItr || '',
      weather: journal.weather || '',
      timeStart: journal.timeStart || '',
      timeEnd: journal.timeEnd || '',
      qualityStatus: journal.qualityStatus || '',
      normatives: journal.normatives || '',
      projectDocs: journal.projectDocs || '',
      sectionName: journal.sectionName || '',
      hiddenWork: !!journal.hiddenWork,
    };
    await fetch(API + '/work-journal/' + journal.id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    setWorkJournal(prev => prev.map(item => item.id === journal.id ? {...item, ...body, aiFilled: false} : item));
    setEditingJournal(null);
  };

  const openHiddenAct = () => {
    const matchingAct = hiddenActs.find(act => (
      act.projectName === journal.project && (act.workName || '').trim() === (journal.description || '').trim()
    ));
    if (matchingAct) {
      setEditingJournal(null);
      setEditingAct(matchingAct);
      return;
    }
    alert('Печатная форма АОСР для этой записи пока не создана. Она появляется из сметы: отметьте позицию 🔒 и заполните «Сделано».');
  };

  return (
    <div onClick={() => setEditingJournal(null)} style={{position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.55)', zIndex: 1600, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'}}>
      <div onClick={event => event.stopPropagation()} style={{...card, padding: 0, width: 'min(900px,100%)', maxHeight: '92vh', display: 'flex', flexDirection: 'column', overflow: 'hidden'}}>
        <div style={{padding: '16px 20px', borderBottom: '1.5px solid ' + C.border, backgroundColor: C.bg, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px'}}>
          <div>
            <b style={{color: C.text, fontSize: '16px', display: 'block'}}>📖 Запись журнала производства работ</b>
            <span style={{fontSize: '12px', color: C.textSec}}>{(journal.project || '—') + ' · ' + (journal.date || '—') + ' · ' + (journal.masterName || '—')}</span>
          </div>
          <div style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
            <span style={{
              padding: '4px 10px',
              borderRadius: '12px',
              fontSize: '12px',
              fontWeight: '600',
              backgroundColor: journal.status === 'Подтверждено' ? C.successLight : journal.status === 'Отклонено' ? C.dangerLight : C.warningLight,
              color: journal.status === 'Подтверждено' ? C.success : journal.status === 'Отклонено' ? C.danger : C.warning,
            }}>
              {journal.status || '—'}
            </span>
            <button onClick={() => setEditingJournal(null)} style={{...btnG, padding: '5px 10px'}}>
              <X size={14}/>
            </button>
          </div>
        </div>

        <div style={{flex: 1, overflowY: 'auto', padding: '18px 20px'}}>
          {journal.aiFilled && (
            <div style={aiNotice}>
              <span style={aiNoticeIcon}>🤖</span>
              <span style={aiNoticeText}><b>Поля заполнены AI.</b> Проверь нормативы и проектные документы — при сохранении после правки метка снимется.</span>
            </div>
          )}

          <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '10px', marginBottom: '18px', padding: '12px', backgroundColor: C.bg, borderRadius: '10px', border: '1.5px solid ' + C.border}}>
            <div><p style={labelStyle}>Раздел сметы</p><b style={{fontSize: '13px', color: C.text}}>{journal.sectionName || '—'}</b></div>
            <div><p style={labelStyle}>Работа</p><b style={{fontSize: '13px', color: C.text}}>{journal.description}</b></div>
            <div><p style={labelStyle}>Исполнитель</p><b style={{fontSize: '13px', color: C.text}}>{journal.masterName || '—'}</b></div>
            <div><p style={labelStyle}>Объём</p><b style={{fontSize: '13px', color: C.text}}>{fmtMeasure(journal.quantity, journal.unit)}</b></div>
            <div><p style={labelStyle}>Сумма</p><b style={{fontSize: '14px', color: C.accent}}>{Number(journal.total || 0).toLocaleString('ru-RU') + ' ₽'}</b></div>
            <div><p style={labelStyle}>Дата</p><b style={{fontSize: '13px', color: C.text}}>{journal.date || '—'}</b></div>
          </div>

          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '14px'}}>
            <div>
              <label style={labelStyle}>Ответственный ИТР (прораб)</label>
              <input list="jrnl-itr-list" value={journal.responsibleItr || ''} onChange={event => updateJournal('responsibleItr', event.target.value)} placeholder="ФИО прораба или инженера" style={inp}/>
              <datalist id="jrnl-itr-list">{prorabNames.map(name => <option key={name} value={name}/>)}</datalist>
            </div>
            <div>
              <label style={labelStyle}>Статус</label>
              <select value={journal.status || 'На проверке'} onChange={event => updateJournal('status', event.target.value)} style={inp}>
                <option>На проверке</option>
                <option>Подтверждено</option>
                <option>Отклонено</option>
              </select>
            </div>
          </div>

          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr 2fr', gap: '10px', marginBottom: '14px'}}>
            <div><label style={labelStyle}>Начало работы</label><input type="time" value={journal.timeStart || ''} onChange={event => updateJournal('timeStart', event.target.value)} style={inp}/></div>
            <div><label style={labelStyle}>Окончание</label><input type="time" value={journal.timeEnd || ''} onChange={event => updateJournal('timeEnd', event.target.value)} style={inp}/></div>
            <div>
              <label style={labelStyle}>Метеоусловия (температура, осадки, ветер)</label>
              <div style={{display: 'flex', gap: '4px'}}>
                <input value={journal.weather || ''} onChange={event => updateJournal('weather', event.target.value)} placeholder="напр. +12°C, без осадков, ветер 3 м/с" style={{...inp, marginBottom: 0, flex: 1}}/>
                {todayWeather && (
                  <button onClick={() => updateJournal('weather', (todayWeather.condition || '') + ', ' + (todayWeather.temperature || '') + '°C, ветер ' + (todayWeather.windSpeed || '') + ' м/с')} title="Подтянуть из журнала погоды" style={{...btnG, padding: '5px 10px', fontSize: '11px'}}>📡</button>
                )}
              </div>
            </div>
          </div>

          <div style={sectionStyle}>
            <label style={labelStyle}>Качество / соответствие проекту</label>
            <select value={journal.qualityStatus || ''} onChange={event => updateJournal('qualityStatus', event.target.value)} style={inp}>
              <option value="">— не указано —</option>
              <option>Соответствует проекту</option>
              <option>Соответствует с замечаниями</option>
              <option>Не соответствует</option>
            </select>
          </div>

          <div style={sectionStyle}>
            <label style={labelStyle}>Применимые нормативы (СНиП/СП/ГОСТ){journal.aiFilled ? ' 🤖' : ''}</label>
            <textarea value={journal.normatives || ''} onChange={event => updateJournal('normatives', event.target.value)} placeholder="Напр.: СП 71.13330.2017, ГОСТ 30693-2000" style={{...inp, minHeight: '60px', resize: 'vertical'}}/>
          </div>
          <div style={sectionStyle}>
            <label style={labelStyle}>Проектная документация (разделы, листы){journal.aiFilled ? ' 🤖' : ''}</label>
            <textarea value={journal.projectDocs || ''} onChange={event => updateJournal('projectDocs', event.target.value)} placeholder="Напр.: раздел КЖ, лист 12; раздел АР, узел 4" style={{...inp, minHeight: '60px', resize: 'vertical'}}/>
          </div>
          <div style={sectionStyle}>
            <label style={labelStyle}>Использованные материалы</label>
            <div style={{padding: '10px', backgroundColor: C.bg, borderRadius: '8px', border: '1.5px solid ' + C.border, fontSize: '12px', color: C.textSec, whiteSpace: 'pre-wrap'}}>
              {journal.materialsUsed ? (typeof journal.materialsUsed === 'string' ? journal.materialsUsed : JSON.stringify(journal.materialsUsed)) : '(не указаны)'}
            </div>
          </div>
          <div style={sectionStyle}>
            <label style={labelStyle}>Комментарий / заключение</label>
            <textarea value={journal.comment || ''} onChange={event => updateJournal('comment', event.target.value)} placeholder="Замечания, особенности производства работ, ссылки на акты" style={{...inp, minHeight: '70px', resize: 'vertical'}}/>
          </div>

          {journal.hiddenWork && (
            <div style={{padding: '10px 12px', backgroundColor: C.bg, border: '1.5px solid ' + C.border, borderRadius: '8px', fontSize: '12px', color: C.textSec, marginBottom: '10px'}}>
              🔒 По этой записи доступна печатная форма АОСР. Проверьте реквизиты и распечатайте акт для исполнительной документации.
            </div>
          )}
        </div>

        <div style={{padding: '14px 20px', borderTop: '1.5px solid ' + C.border, backgroundColor: C.bg, display: 'flex', gap: '8px', justifyContent: 'space-between', flexWrap: 'wrap'}}>
          <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap'}}>
            <button onClick={() => showPreview(buildWorkJournalContent([journal], journal.project, journal.date, journal.date), 'Запись журнала')} style={btnB}>
              <Eye size={14}/>🖨️ Печать
            </button>
            {journal.hiddenWork && (
              <button onClick={openHiddenAct} style={{...btnB, backgroundColor: '#10b981', color: 'white', borderColor: '#059669'}}>🔒 АОСР / печать</button>
            )}
          </div>
          <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap'}}>
            <button disabled={!!journal.__aiLoading} onClick={fillByAI} style={{...btnB, backgroundColor: '#10b981', color: 'white', borderColor: '#059669', opacity: journal.__aiLoading ? 0.6 : 1, cursor: journal.__aiLoading ? 'not-allowed' : 'pointer'}}>
              <Bot size={14}/>{journal.__aiLoading ? 'AI работает…' : (journal.aiFilled ? '🤖 Перезаполнить AI' : '🤖 Заполнить через AI')}
            </button>
            <button onClick={() => setEditingJournal(null)} style={btnG}>Отмена</button>
            <button onClick={saveJournal} style={btnO}>
              <Check size={14}/>Сохранить
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
