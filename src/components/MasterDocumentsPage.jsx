import React from 'react';
import { CheckCircle, Eye, Printer, Upload } from 'lucide-react';
import ProjectHiddenWorksActSignatureModal from './ProjectHiddenWorksActSignatureModal';

export default function MasterDocumentsPage({
  API,
  C,
  btnB,
  btnO,
  buildActContent,
  buildContractContent,
  buildHiddenActContent,
  card,
  doPrint,
  fileSrc,
  hiddenActs = [],
  editingHiddenAct,
  masterProfile,
  masterProfiles,
  myActs,
  myContract,
  myTools,
  pdConsents,
  PD_CONSENT_TEXT,
  refreshData,
  setEditingHiddenAct,
  setHiddenActs,
  showPreview,
  uploadPhoto,
  user,
  btnG,
  inp,
}) {
  const consentHtml = PD_CONSENT_TEXT({
    fullName: masterProfile?.fullName || user.name,
    passport: masterProfile?.passport || '',
    inn: masterProfile?.inn || '',
  });
  const consent = pdConsents.find((item) => item.userId === user.id);
  const actorKey = String(user.name || '').trim().toLowerCase();
  const normalizedContract = myContract ? {
    ...myContract,
    contractNumber: myContract.contractNumber || myContract.contract_number || myContract.number || myContract.id || '',
    contractType: myContract.contractType || myContract.contract_type || myContract.contractorType || 'Договор субподряда',
    project: myContract.project || myContract.projectName || myContract.project_name || '',
  } : null;
  const myHiddenActs = (hiddenActs || []).filter((act) => {
    const names = [act.brigade, act.signedContractor, act.signedSubcontractor]
      .map((value) => String(value || '').trim().toLowerCase())
      .filter(Boolean);
    return names.includes(actorKey);
  });

  return (
    <div>
      <h3 style={{ color: C.text, marginBottom: '20px', fontSize: '18px', fontWeight: '700' }}>Мои документы</h3>
      <div style={{ ...card, padding: '20px', marginBottom: '15px' }}>
        <h4 style={{ color: C.text, marginBottom: '10px', fontSize: '14px', fontWeight: '600' }}>📋 Согласие на обработку ПД</h4>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '10px', flexWrap: 'wrap' }}>
          <button onClick={() => showPreview(consentHtml, 'Согласие на ПД')} style={btnB}>
            <Eye size={14} />
            Просмотр
          </button>
          <button onClick={() => doPrint(consentHtml)} style={btnO}>
            <Printer size={14} />
            Распечатать
          </button>
        </div>
        {consent?.scanUrl ? (
          <div style={{ backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder, padding: '10px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <CheckCircle size={16} color={C.success} />
            <span style={{ color: C.success, fontSize: '13px' }}>Скан загружен</span>
          </div>
        ) : (
          <label style={{ cursor: 'pointer', backgroundColor: C.infoLight, padding: '10px', borderRadius: '8px', fontSize: '13px', color: C.info, border: '1.5px solid ' + C.infoBorder, display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
            <Upload size={14} />
            Загрузить скан
            <input
              type="file"
              accept="image/*,application/pdf"
              style={{ display: 'none' }}
              onChange={async (e) => {
                if (!e.target.files?.[0]) return;
                const url = await uploadPhoto(e.target.files[0], { context: 'pd-consents' });
                await fetch(API + '/pd-consents', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    userId: user.id,
                    signedAt: new Date().toLocaleString('ru-RU'),
                    scanUrl: url,
                    uploadedBy: user.name,
                  }),
                });
                await refreshData();
              }}
            />
          </label>
        )}
      </div>

      <div style={{ ...card, padding: '20px', marginBottom: '15px' }}>
        <h4 style={{ color: C.text, marginBottom: '10px', fontSize: '14px', fontWeight: '600' }}>📄 Мой договор</h4>
        {normalizedContract ? (
          <div>
            <p style={{ color: C.textSec, fontSize: '13px' }}>{'Договор № ' + normalizedContract.contractNumber + ' · ' + normalizedContract.contractType + ' · ' + normalizedContract.project}</p>
            <button
              onClick={() => {
                const profile = masterProfiles.find((item) => item.userId === user.id);
                if (profile) showPreview(buildContractContent(profile, normalizedContract), 'Договор');
              }}
              style={{ ...btnB, marginTop: '8px' }}
            >
              <Eye size={14} />
              Просмотр
            </button>
          </div>
        ) : (
          <p style={{ color: C.textMuted, fontSize: '13px' }}>Договор не найден</p>
        )}
      </div>

      <div style={{ ...card, padding: '20px' }}>
        <h4 style={{ color: C.text, marginBottom: '10px', fontSize: '14px', fontWeight: '600' }}>📋 Мои акты</h4>
        {myActs.map((act) => {
          const totalAmt = act.totalAmount || 0;
          const paidAmt = act.paidAmount || 0;
          const toolDed = myTools.filter((tool) => tool.issueType === 'В счёт зарплаты').reduce((sum, tool) => sum + tool.cost, 0);
          const rest = totalAmt - toolDed - paidAmt;
          return (
            <div key={act.id} style={{ padding: '12px', backgroundColor: C.bg, borderRadius: '8px', marginBottom: '8px', border: '1.5px solid ' + C.border }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <div>
                  <b style={{ fontSize: '13px', color: C.text }}>{'Акт №' + act.id}</b>
                  <p style={{ color: C.textSec, margin: '2px 0', fontSize: '12px' }}>{act.project + ' · ' + act.periodStart + ' — ' + act.periodEnd}</p>
                  <p style={{ color: C.text, margin: '1px 0', fontSize: '12px' }}>{'Начислено: ' + totalAmt.toLocaleString() + ' ₽'}</p>
                  {toolDed > 0 && <p style={{ color: C.danger, margin: '1px 0', fontSize: '12px' }}>{'Удержания: -' + toolDed.toLocaleString() + ' ₽'}</p>}
                  <p style={{ color: C.success, margin: '1px 0', fontSize: '12px' }}>{'Оплачено: ' + paidAmt.toLocaleString() + ' ₽'}</p>
                  {rest > 0 && <p style={{ color: C.danger, margin: '1px 0', fontSize: '12px', fontWeight: '600' }}>{'Остаток: ' + rest.toLocaleString() + ' ₽'}</p>}
                </div>
                <button onClick={() => showPreview(buildActContent(act), 'Акт')} style={btnB}>
                  <Eye size={14} />
                </button>
              </div>
            </div>
          );
        })}
        {myActs.length === 0 && <p style={{ color: C.textMuted, fontSize: '13px' }}>Актов нет</p>}
      </div>

      <div style={{ ...card, padding: '20px', marginTop: '15px' }}>
        <h4 style={{ color: C.text, marginBottom: '10px', fontSize: '14px', fontWeight: '600' }}>🔒 АОСР на подпись</h4>
        {myHiddenActs.map((act) => (
          <div key={act.id} style={{ padding: '12px', backgroundColor: C.bg, borderRadius: '8px', marginBottom: '8px', border: '1.5px solid ' + C.border }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <b style={{ fontSize: '13px', color: C.text }}>{act.actNumber || 'АОСР'} · {act.workName || 'Работа'}</b>
                <p style={{ color: C.textSec, margin: '3px 0', fontSize: '12px' }}>
                  {(act.projectName || '—') + ' · ' + (act.quantity || 0) + ' ' + (act.unit || '') + ' · ' + (act.workDate || 'без даты')}
                </p>
                <span style={{
                  display: 'inline-flex',
                  padding: '2px 8px',
                  borderRadius: '10px',
                  fontSize: '11px',
                  fontWeight: 700,
                  backgroundColor: act.signedSubcontractor ? C.successLight : C.warningLight,
                  color: act.signedSubcontractor ? C.success : C.warning,
                }}>
                  {act.signedSubcontractor ? 'Подписано исполнителем' : 'Нужна подпись исполнителя'}
                </span>
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                <button onClick={() => setEditingHiddenAct(act)} style={{ ...btnB, padding: '6px 10px', fontSize: '12px' }}>
                  <CheckCircle size={13} />
                  Подписать
                </button>
                <button onClick={() => showPreview(buildHiddenActContent(act), 'АОСР № ' + (act.actNumber || act.id))} style={{ ...btnO, padding: '6px 10px', fontSize: '12px' }}>
                  <Printer size={13} />
                  Печать
                </button>
              </div>
            </div>
          </div>
        ))}
        {myHiddenActs.length === 0 && <p style={{ color: C.textMuted, fontSize: '13px' }}>АОСР на подпись нет</p>}
      </div>

      <ProjectHiddenWorksActSignatureModal
        act={editingHiddenAct}
        mode="executor"
        setEditingAct={setEditingHiddenAct}
        setHiddenActs={setHiddenActs}
        C={C}
        card={card}
        inp={inp}
        btnG={btnG}
        btnO={btnO}
      />
    </div>
  );
}
