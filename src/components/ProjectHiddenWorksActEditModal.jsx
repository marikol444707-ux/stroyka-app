import React from 'react';
import { Bot, Camera, Check, Eye, Image as ImageIcon, Upload, X } from 'lucide-react';
import { API } from '../api';

export default function ProjectHiddenWorksActEditModal({
  act,
  setEditingAct,
  setHiddenActs,
  setShowPhotoModal,
  uploadPhoto,
  fileSrc,
  showPreview,
  buildHiddenActContent,
  C,
  card,
  inp,
  btnB,
  btnG,
  btnO,
  btnR,
  aiNotice,
  aiNoticeIcon,
  aiNoticeText,
}) {
  if (!act) return null;

  const updateAct = (key, value) => setEditingAct({...act, [key]: value});
  const photos = (act.photos || '').split(',').filter(Boolean);
  const certificates = (act.certificates || '').split(',').filter(Boolean);
  const labelStyle = {fontSize: '11px', color: C.textSec, fontWeight: '600', marginBottom: '4px', display: 'block'};
  const sectionStyle = {marginBottom: '14px'};
  const allSigned = !!(act.signedCustomer && act.signedSupervisor && act.signedContractor && act.signedSubcontractor);
  const absoluteUrl = url => fileSrc(url);

  const fillByAI = async () => {
    setEditingAct(prev => ({...prev, __aiLoading: true}));
    try {
      const res = await fetch(API + '/hidden-works-acts/' + act.id + '/ai-prefill', {method: 'POST'});
      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.detail || ('HTTP ' + res.status));
      }
      const data = await res.json();
      setEditingAct(prev => ({
        ...prev,
        conclusion: data.conclusion || prev.conclusion,
        projectDocs: data.projectDocs || prev.projectDocs,
        aiFilled: true,
        __aiLoading: false,
      }));
      setHiddenActs(prevList => prevList.map(item => (
        item.id === act.id
          ? {...item, conclusion: data.conclusion || item.conclusion, projectDocs: data.projectDocs || item.projectDocs, aiFilled: true}
          : item
      )));
    } catch (error) {
      alert('Не получилось получить ответ от AI: ' + error.message);
      setEditingAct(prev => ({...prev, __aiLoading: false}));
    }
  };

  const saveAct = async () => {
    const body = {
      status: act.status || 'Черновик',
      signedCustomer: act.signedCustomer || '',
      signedSupervisor: act.signedSupervisor || '',
      signedContractor: act.signedContractor || '',
      signedSubcontractor: act.signedSubcontractor || '',
      signedCustomerAt: act.signedCustomerAt || '',
      signedSupervisorAt: act.signedSupervisorAt || '',
      signedContractorAt: act.signedContractorAt || '',
      signedSubcontractorAt: act.signedSubcontractorAt || '',
      conclusion: act.conclusion || '',
      comments: act.comments || '',
      materialsUsed: act.materialsUsed || '',
      projectDocs: act.projectDocs || '',
      photos: act.photos || '',
      certificates: act.certificates || '',
      city: act.city || '',
    };
    const res = await fetch(API + '/hidden-works-acts/' + act.id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(data.detail || data.error || 'Не удалось сохранить акт');
      return;
    }
    const newStatus = data.status || act.status;
    const updated = {...act, status: newStatus, aiFilled: false};
    setHiddenActs(prev => prev.map(item => item.id === act.id ? updated : item));
    setEditingAct(null);
  };

  const openHistory = async () => {
    setEditingAct(prev => ({...prev, __versionsLoading: true, __versionsOpen: true}));
    try {
      const res = await fetch(API + '/document-versions?document_type=hidden_works_act&document_id=' + act.id);
      const list = await res.json();
      setEditingAct(prev => ({
        ...prev,
        __versionsList: Array.isArray(list) ? list : [],
        __versionsLoading: false,
        __viewingVer: null,
      }));
    } catch {
      setEditingAct(prev => ({...prev, __versionsList: [], __versionsLoading: false}));
    }
  };

  const viewVersion = async versionId => {
    setEditingAct(prev => ({...prev, __viewingVerLoading: true}));
    try {
      const res = await fetch(API + '/document-versions/' + versionId);
      const version = await res.json();
      setEditingAct(prev => ({...prev, __viewingVer: version, __viewingVerLoading: false}));
    } catch {
      setEditingAct(prev => ({...prev, __viewingVerLoading: false}));
    }
  };

  const uploadActPhotos = async files => {
    const next = [...photos];
    for (const file of Array.from(files || [])) {
      const url = await uploadPhoto(file, {projectName: act.projectName, context: 'hidden-works-acts'});
      if (url) next.push(url);
    }
    updateAct('photos', next.join(','));
  };

  const uploadCertificates = async files => {
    const next = [...certificates];
    for (const file of Array.from(files || [])) {
      const url = await uploadPhoto(file, {projectName: act.projectName, context: 'hidden-works-acts-certificates'});
      if (url) next.push(url);
    }
    updateAct('certificates', next.join(','));
  };

  const removePhoto = index => updateAct('photos', photos.filter((_, itemIndex) => itemIndex !== index).join(','));
  const removeCertificate = index => updateAct('certificates', certificates.filter((_, itemIndex) => itemIndex !== index).join(','));

  return (
    <>
      <div onClick={() => setEditingAct(null)} style={{position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.55)', zIndex: 1600, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'}}>
        <div onClick={event => event.stopPropagation()} style={{...card, padding: 0, width: 'min(900px,100%)', maxHeight: '92vh', display: 'flex', flexDirection: 'column', overflow: 'hidden'}}>
          <div style={{padding: '16px 20px', borderBottom: '1.5px solid ' + C.border, backgroundColor: C.bg, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px'}}>
            <div>
              <b style={{color: C.text, fontSize: '16px', display: 'block'}}>🔒 {act.actNumber}</b>
              <span style={{fontSize: '12px', color: C.textSec}}>Акт освидетельствования скрытых работ · {act.projectName}</span>
            </div>
            <div style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
              <span style={{
                padding: '4px 10px',
                borderRadius: '12px',
                fontSize: '12px',
                fontWeight: '600',
                backgroundColor: allSigned ? C.successLight : C.warningLight,
                color: allSigned ? C.success : C.warning,
              }}>
                {allSigned ? 'Подписан' : (act.status || 'Черновик')}
              </span>
              <button onClick={openHistory} style={{...btnG, padding: '5px 10px', fontSize: '12px'}} title="История изменений">📜 История</button>
              <button onClick={() => setEditingAct(null)} style={{...btnG, padding: '5px 10px'}}><X size={14}/></button>
            </div>
          </div>

          <div style={{flex: 1, overflowY: 'auto', padding: '18px 20px'}}>
            {act.aiFilled && (
              <div style={aiNotice}>
                <span style={aiNoticeIcon}>🤖</span>
                <span style={aiNoticeText}><b>Черновик заполнен AI.</b> Проверьте формулировки перед подписью — при сохранении после правки метка снимется.</span>
              </div>
            )}

            <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '10px', marginBottom: '18px', padding: '12px', backgroundColor: C.bg, borderRadius: '10px', border: '1.5px solid ' + C.border}}>
              <div><p style={labelStyle}>Раздел сметы</p><b style={{fontSize: '13px', color: C.text}}>{act.sectionName || '—'}</b></div>
              <div><p style={labelStyle}>Работа</p><b style={{fontSize: '13px', color: C.text}}>{act.workName}</b></div>
              <div><p style={labelStyle}>Бригада</p><b style={{fontSize: '13px', color: C.text}}>{act.brigade || '—'}</b></div>
              <div><p style={labelStyle}>Объём</p><b style={{fontSize: '13px', color: C.text}}>{Number(act.quantity || 0).toLocaleString('ru-RU') + ' ' + (act.unit || '')}</b></div>
              <div><p style={labelStyle}>Цена за ед.</p><b style={{fontSize: '13px', color: C.text}}>{Number(act.pricePerUnit || 0).toLocaleString('ru-RU') + ' ₽'}</b></div>
              <div><p style={labelStyle}>Сумма</p><b style={{fontSize: '14px', color: C.accent}}>{Number(act.total || 0).toLocaleString('ru-RU') + ' ₽'}</b></div>
              <div><p style={labelStyle}>Дата работ</p><b style={{fontSize: '13px', color: C.text}}>{act.workDate || '—'}</b></div>
            </div>

            <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '14px'}}>
              <div>
                <label style={labelStyle}>Город (для печати)</label>
                <input value={act.city || ''} onChange={event => updateAct('city', event.target.value)} placeholder="напр. г. Барнаул" style={inp}/>
              </div>
              <div>
                <label style={labelStyle}>Статус (вручную)</label>
                <select value={act.status || 'Черновик'} onChange={event => updateAct('status', event.target.value)} style={inp}>
                  <option>Черновик</option>
                  <option>На подписи</option>
                  <option>Подписан</option>
                  <option>Аннулирован</option>
                </select>
              </div>
            </div>

            <div style={sectionStyle}>
              <label style={labelStyle}>Использованные материалы (марки, сертификаты)</label>
              <textarea value={act.materialsUsed || ''} onChange={event => updateAct('materialsUsed', event.target.value)} placeholder="Напр.: арматура А500С по ГОСТ 5781-82, сертификат №...; бетон В25 W6, паспорт №..." style={{...inp, minHeight: '70px', resize: 'vertical'}}/>
            </div>
            <div style={sectionStyle}>
              <label style={labelStyle}>Проектная документация (чертежи, разделы){act.aiFilled ? ' 🤖' : ''}</label>
              <textarea value={act.projectDocs || ''} onChange={event => updateAct('projectDocs', event.target.value)} placeholder="Напр.: раздел КЖ, лист 12; раздел АР, узел 4" style={{...inp, minHeight: '60px', resize: 'vertical'}}/>
            </div>
            <div style={sectionStyle}>
              <label style={labelStyle}>Заключение комиссии{act.aiFilled ? ' 🤖' : ''}</label>
              <textarea value={act.conclusion || ''} onChange={event => updateAct('conclusion', event.target.value)} placeholder="Работы выполнены в соответствии с проектной документацией. Разрешается производство последующих работ." style={{...inp, minHeight: '70px', resize: 'vertical'}}/>
            </div>

            <div style={{...sectionStyle, padding: '14px', backgroundColor: C.bg, borderRadius: '10px', border: '1.5px solid ' + C.border}}>
              <b style={{display: 'block', marginBottom: '10px', color: C.text, fontSize: '13px'}}>✍️ Подписи комиссии (ФИО + дата)</b>
              {[
                {role: 'Заказчик', field: 'signedCustomer', dateField: 'signedCustomerAt'},
                {role: 'Технадзор', field: 'signedSupervisor', dateField: 'signedSupervisorAt'},
                {role: 'Генподрядчик', field: 'signedContractor', dateField: 'signedContractorAt'},
                {role: 'Субподрядчик', field: 'signedSubcontractor', dateField: 'signedSubcontractorAt'},
              ].map(signature => (
                <div key={signature.field} style={{display: 'grid', gridTemplateColumns: '140px 1fr 140px', gap: '8px', marginBottom: '8px', alignItems: 'center'}}>
                  <span style={{fontSize: '12px', color: C.textSec, fontWeight: '600'}}>{signature.role}:</span>
                  <input value={act[signature.field] || ''} onChange={event => updateAct(signature.field, event.target.value)} placeholder="ФИО, должность, организация" style={{...inp, marginBottom: 0}}/>
                  <input type="date" value={act[signature.dateField] || ''} onChange={event => updateAct(signature.dateField, event.target.value)} style={{...inp, marginBottom: 0}}/>
                </div>
              ))}
              <p style={{fontSize: '11px', color: C.textMuted, margin: '8px 0 0', lineHeight: 1.4}}>Подписи можно заполнить для контроля. Если стороны подписали акт вне системы, переведите статус в «Подписан» вручную.</p>
            </div>

            <div style={sectionStyle}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px'}}>
                <b style={{color: C.text, fontSize: '13px'}}>📷 Фото скрытых работ ({photos.length})</b>
                <div style={{display: 'flex', gap: '6px', flexWrap: 'wrap'}}>
                  <label style={{...btnB, padding: '5px 10px', fontSize: '12px', cursor: 'pointer'}}>
                    <ImageIcon size={12}/>Галерея
                    <input type="file" accept="image/*" multiple style={{display: 'none'}} onChange={async event => { await uploadActPhotos(event.target.files); event.target.value = ''; }}/>
                  </label>
                  <label style={{...btnB, padding: '5px 10px', fontSize: '12px', cursor: 'pointer'}}>
                    <Camera size={12}/>Камера
                    <input type="file" accept="image/*" capture="environment" style={{display: 'none'}} onChange={async event => { await uploadActPhotos(event.target.files); event.target.value = ''; }}/>
                  </label>
                </div>
              </div>
              {photos.length === 0 ? (
                <p style={{color: C.textMuted, fontSize: '12px', margin: 0}}>Фотографий не загружено</p>
              ) : (
                <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(90px,1fr))', gap: '8px'}}>
                  {photos.map((url, index) => (
                    <div key={index} style={{position: 'relative'}}>
                      <img src={absoluteUrl(url)} alt="" onClick={() => setShowPhotoModal(absoluteUrl(url))} style={{width: '100%', height: '90px', borderRadius: '8px', objectFit: 'cover', cursor: 'pointer', border: '1.5px solid ' + C.border}}/>
                      <button onClick={() => removePhoto(index)} style={{position: 'absolute', top: '2px', right: '2px', backgroundColor: 'rgba(0,0,0,0.6)', color: 'white', border: 'none', borderRadius: '50%', width: '20px', height: '20px', cursor: 'pointer', fontSize: '11px'}}>×</button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div style={sectionStyle}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px'}}>
                <b style={{color: C.text, fontSize: '13px'}}>📄 Сертификаты и документы ({certificates.length})</b>
                <div style={{display: 'flex', gap: '6px', flexWrap: 'wrap'}}>
                  <label style={{...btnB, padding: '5px 10px', fontSize: '12px', cursor: 'pointer'}}>
                    <Upload size={12}/>Файл
                    <input type="file" accept=".pdf,.xlsx,.xls,.doc,.docx,image/*" multiple style={{display: 'none'}} onChange={async event => { await uploadCertificates(event.target.files); event.target.value = ''; }}/>
                  </label>
                  <label style={{...btnB, padding: '5px 10px', fontSize: '12px', cursor: 'pointer'}}>
                    <Camera size={12}/>Камера
                    <input type="file" accept="image/*" capture="environment" style={{display: 'none'}} onChange={async event => { await uploadCertificates(event.target.files); event.target.value = ''; }}/>
                  </label>
                </div>
              </div>
              {certificates.length === 0 ? (
                <p style={{color: C.textMuted, fontSize: '12px', margin: 0}}>Файлов не прикреплено</p>
              ) : (
                <div style={{display: 'flex', flexDirection: 'column', gap: '4px'}}>
                  {certificates.map((url, index) => {
                    const name = url.split('/').pop() || url;
                    return (
                      <div key={index} style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', backgroundColor: C.bg, border: '1.5px solid ' + C.border, borderRadius: '8px'}}>
                        <a href={absoluteUrl(url)} target="_blank" rel="noreferrer" style={{color: C.accent, fontSize: '12px', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px', flex: 1, overflow: 'hidden'}}>
                          <span>📄</span><span style={{overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>{name}</span>
                        </a>
                        <button onClick={() => removeCertificate(index)} style={{...btnR, padding: '3px 7px', fontSize: '11px'}}><X size={10}/></button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div style={sectionStyle}>
              <label style={labelStyle}>Комментарии (внутренние)</label>
              <textarea value={act.comments || ''} onChange={event => updateAct('comments', event.target.value)} placeholder="Внутренние пометки, не печатаются" style={{...inp, minHeight: '50px', resize: 'vertical'}}/>
            </div>
          </div>

          <div style={{padding: '14px 20px', borderTop: '1.5px solid ' + C.border, backgroundColor: C.bg, display: 'flex', gap: '8px', justifyContent: 'space-between', flexWrap: 'wrap'}}>
            <button onClick={() => showPreview(buildHiddenActContent(act), 'АОСР № ' + act.actNumber)} style={btnB}>
              <Eye size={14}/>🖨️ Печать по СНиП
            </button>
            <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap'}}>
              <button disabled={!!act.__aiLoading} onClick={fillByAI} style={{...btnB, backgroundColor: '#10b981', color: 'white', borderColor: '#059669', opacity: act.__aiLoading ? 0.6 : 1, cursor: act.__aiLoading ? 'not-allowed' : 'pointer'}}>
                <Bot size={14}/>{act.__aiLoading ? 'AI работает…' : (act.aiFilled ? '🤖 Перезаполнить AI' : '🤖 Заполнить через AI')}
              </button>
              <button onClick={() => setEditingAct(null)} style={btnG}>Отмена</button>
              <button onClick={saveAct} style={btnO}><Check size={14}/>Сохранить</button>
            </div>
          </div>
        </div>
      </div>

      {act.__versionsOpen && (
        <div onClick={() => setEditingAct(prev => ({...prev, __versionsOpen: false, __viewingVer: null}))} style={{position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.6)', zIndex: 1700, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'}}>
          <div onClick={event => event.stopPropagation()} style={{...card, padding: 0, width: 'min(900px,100%)', maxHeight: '88vh', display: 'flex', flexDirection: 'column', overflow: 'hidden'}}>
            <div style={{padding: '14px 18px', borderBottom: '1.5px solid ' + C.border, backgroundColor: C.bg, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
              <div>
                <b style={{color: C.text, fontSize: '15px', display: 'block'}}>📜 История версий</b>
                <span style={{fontSize: '11px', color: C.textSec}}>АОСР № {act.actNumber} · {(act.__versionsList || []).length} снимков</span>
              </div>
              <button onClick={() => setEditingAct(prev => ({...prev, __versionsOpen: false, __viewingVer: null}))} style={{...btnG, padding: '5px 10px'}}><X size={14}/></button>
            </div>
            <div style={{flex: 1, overflowY: 'auto', display: 'flex'}}>
              <div style={{width: '320px', borderRight: '1.5px solid ' + C.border, overflowY: 'auto'}}>
                {act.__versionsLoading ? (
                  <p style={{color: C.textMuted, padding: '16px', fontSize: '12px', textAlign: 'center'}}>Загрузка…</p>
                ) : (act.__versionsList || []).length === 0 ? (
                  <p style={{color: C.textMuted, padding: '16px', fontSize: '12px', textAlign: 'center'}}>История пуста.<br/>Снимки делаются при каждом изменении акта.</p>
                ) : (
                  (act.__versionsList || []).map(version => (
                    <div key={version.id} onClick={() => viewVersion(version.id)} style={{padding: '10px 14px', borderBottom: '1px solid ' + C.border, cursor: 'pointer', backgroundColor: act.__viewingVer && act.__viewingVer.id === version.id ? C.infoLight : 'transparent'}}>
                      <b style={{fontSize: '12px', color: C.text, display: 'block'}}>{version.versionLabel}</b>
                      <span style={{fontSize: '10px', color: C.textSec, display: 'block'}}>{version.createdAt}</span>
                      {version.changedBy && <span style={{fontSize: '10px', color: C.textMuted, display: 'block'}}>👤 {version.changedBy}</span>}
                      {version.changeReason && <span style={{fontSize: '10px', color: C.textMuted, display: 'block'}}>📝 {version.changeReason}</span>}
                    </div>
                  ))
                )}
              </div>
              <div style={{flex: 1, overflowY: 'auto', padding: '14px 18px', backgroundColor: C.bg}}>
                {act.__viewingVerLoading ? (
                  <p style={{color: C.textMuted, fontSize: '12px'}}>Загрузка снимка…</p>
                ) : !act.__viewingVer ? (
                  <p style={{color: C.textMuted, fontSize: '12px'}}>← Выберите версию слева чтобы посмотреть состояние акта на тот момент</p>
                ) : (
                  <VersionSnapshotTable version={act.__viewingVer} C={C}/>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function VersionSnapshotTable({version, C}) {
  const snapshot = version.snapshot || {};
  const rows = [
    ['Номер акта', snapshot.act_number],
    ['Проект', snapshot.project_name],
    ['Работа', snapshot.work_name],
    ['Раздел', snapshot.section_name],
    ['Бригада', snapshot.brigade],
    ['Объём', (snapshot.quantity || '') + ' ' + (snapshot.unit || '')],
    ['Цена', snapshot.price_per_unit],
    ['Итого', snapshot.total],
    ['Дата работы', snapshot.work_date],
    ['Статус', snapshot.status],
    ['Заказчик', snapshot.signed_customer],
    ['Технадзор', snapshot.signed_supervisor],
    ['Подрядчик', snapshot.signed_contractor],
    ['Субподряд', snapshot.signed_subcontractor],
    ['Заключение', snapshot.conclusion],
    ['Комментарии', snapshot.comments],
    ['Материалы', snapshot.materials_used],
    ['Проектная док.', snapshot.project_docs],
  ];

  return (
    <div>
      <b style={{fontSize: '13px', color: C.text, display: 'block', marginBottom: '10px'}}>Снимок {version.versionLabel}</b>
      <table style={{width: '100%', fontSize: '11px', borderCollapse: 'collapse'}}>
        <tbody>
          {rows.filter(([, value]) => value !== undefined && value !== null && value !== '').map(([key, value], index) => (
            <tr key={index} style={{borderBottom: '1px solid ' + C.border}}>
              <td style={{padding: '5px 6px', color: C.textSec, fontWeight: '600', width: '130px', verticalAlign: 'top'}}>{key}</td>
              <td style={{padding: '5px 6px', color: C.text}}>{String(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
