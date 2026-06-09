import React from 'react';
import { ArrowLeft, Check, Download, Eye } from 'lucide-react';
import { API } from '../api';
import { buildPerformerContractHtml } from '../utils/contractTemplates';

export default function ProjectBrigadeSelectedHeader({
  projectName,
  selectedBrigadeContract,
  setSelectedBrigadeContract,
  brigadeContractItems = [],
  setBrigadeContractItems,
  setBrigadeContracts,
  setBrigadePayments,
  showPreview,
  companyRequisites,
  companyName,
  staff = [],
  masterProfiles = [],
  users = [],
  C,
  btnG,
  btnO,
  btnB,
}) {
  const closeContract = () => {
    setSelectedBrigadeContract(null);
    setBrigadeContractItems([]);
    setBrigadePayments([]);
  };

  const signContract = async () => {
    const signedAt = new Date().toISOString().split('T')[0];
    const signedContract = {...selectedBrigadeContract, status: 'Подписан', signedAt};

    await fetch(API + '/brigade-contracts/' + selectedBrigadeContract.id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(signedContract),
    });
    setSelectedBrigadeContract(signedContract);
    setBrigadeContracts(prev => prev.map(bc => bc.id === selectedBrigadeContract.id ? signedContract : bc));
  };

  const normalizeKey = (value) => String(value || '').trim().toLowerCase().replace(/\s+/g, ' ');
  const staffPassportText = (s = {}) => {
    const number = [s.passportSeries, s.passportNumber].filter(Boolean).join(' ').trim();
    const issued = [s.passportIssuedBy, s.passportIssuedDate].filter(Boolean).join(', ');
    return [number, issued].filter(Boolean).join('; ');
  };
  const resolvePerformer = () => {
    const id = Number(selectedBrigadeContract.contractorId || 0);
    const nameKey = normalizeKey(selectedBrigadeContract.brigadeName);
    const st = (staff || []).find(s => Number(s.id) === id)
      || (staff || []).find(s => normalizeKey(s.name) === nameKey || normalizeKey(s.brigade) === nameKey)
      || null;
    const userRow = st ? (users || []).find(u => normalizeKey(u.name) === normalizeKey(st.name) || normalizeKey(u.email) === normalizeKey(st.emailWork)) : null;
    const profile = (masterProfiles || []).find(p => Number(p.userId) === id)
      || (userRow ? (masterProfiles || []).find(p => Number(p.userId) === Number(userRow.id)) : null)
      || (masterProfiles || []).find(p => normalizeKey(p.fullName) === nameKey || (st && normalizeKey(p.fullName) === normalizeKey(st.name)))
      || null;
    const type = selectedBrigadeContract.contractorType || profile?.contractType || st?.employmentType || 'Подряд';
    const fullName = profile?.fullName || st?.name || selectedBrigadeContract.brigadeName || 'Исполнитель';
    return {
      ...(st || {}),
      ...(profile || {}),
      fullName,
      name: fullName,
      brigadeName: selectedBrigadeContract.brigadeName || fullName,
      passport: profile?.passport || staffPassportText(st) || '',
      inn: profile?.inn || st?.inn || '',
      bankAccount: profile?.bankAccount || st?.bankAccount || '',
      bankName: profile?.bankName || st?.bankName || '',
      ogrnip: profile?.ogrnip || st?.ogrnip || '',
      phone: profile?.phone || st?.phone || '',
      specialization: profile?.specialization || st?.specialization || st?.role || '',
      contractType: type,
    };
  };
  const missingRequisites = (performer) => {
    const type = String(selectedBrigadeContract.contractorType || performer.contractType || '').toLowerCase();
    const missing = [];
    if (!performer.fullName) missing.push('ФИО/название');
    if (!performer.inn) missing.push('ИНН');
    if ((type.includes('самозан') || type.includes('гпх')) && !performer.passport) missing.push('паспорт');
    if (type.includes('ип') && !performer.ogrnip) missing.push('ОГРНИП');
    if (!type.includes('труд') && !performer.bankAccount) missing.push('расчётный счёт');
    if (!type.includes('труд') && !performer.bankName) missing.push('банк');
    return missing;
  };

  const showContract = () => {
    const total = brigadeContractItems.reduce((sum, item) => sum + item.quantity * item.priceBrigade, 0);
    const performer = resolvePerformer();
    const missing = missingRequisites(performer);
    const html = (missing.length
      ? '<div style="border:1px solid #f59e0b;background:#fff7ed;padding:10px 12px;margin-bottom:12px;border-radius:8px;color:#92400e"><b>Внимание:</b> не хватает реквизитов: ' + missing.join(', ') + '. Заполните карточку исполнителя.</div>'
      : '') + buildPerformerContractHtml({
      company: companyRequisites && companyRequisites.fullName ? companyRequisites : companyName,
      performer,
      contract: {
        ...selectedBrigadeContract,
        id: selectedBrigadeContract.id,
        contractNumber: selectedBrigadeContract.contractNumber || 'БР-' + selectedBrigadeContract.id,
        contractType: selectedBrigadeContract.contractorType,
        project: projectName,
        projectName,
        totalAmount: total || selectedBrigadeContract.totalAmount || selectedBrigadeContract.planAmount || 0,
      },
      items: brigadeContractItems,
    });

    showPreview(html, 'Договор');
  };

  const loadFromPricelist = async () => {
    const res = await fetch(API + '/brigade-contracts/' + selectedBrigadeContract.id + '/load-from-pricelist', {method: 'POST'});
    const data = await res.json();

    if (!res.ok || !data.ok) {
      alert('Ошибка: ' + (data.detail || 'не удалось'));
      return;
    }

    const items = await fetch(API + '/brigade-contract-items/' + selectedBrigadeContract.id).then(r => r.json());
    setBrigadeContractItems(items);
    alert('Загружено позиций: ' + data.itemsLoaded + (data.matchedFromEstimate ? '\nОбъёмы взяты из сметы: ' + data.matchedFromEstimate : ''));
  };

  return (
    <div style={{display: 'flex', gap: '8px', marginBottom: '15px', alignItems: 'center', flexWrap: 'wrap'}}>
      <button onClick={closeContract} style={btnG}><ArrowLeft size={14}/>Назад</button>
      <b style={{color: C.text, fontSize: '14px'}}>{selectedBrigadeContract.brigadeName}</b>
      <span style={{padding: '3px 8px', borderRadius: '6px', fontSize: '11px', backgroundColor: C.accentLight, color: C.accent}}>
        {selectedBrigadeContract.contractorType}
      </span>
      {selectedBrigadeContract.status !== 'Подписан' && (
        <button onClick={signContract} style={btnO}><Check size={14}/>Подписать</button>
      )}
      <button onClick={showContract} style={btnB}><Eye size={14}/>Договор</button>
      {selectedBrigadeContract.pricelistId && (
        <button onClick={loadFromPricelist} style={{border: 'none', borderRadius: '10px', padding: '8px 16px', cursor: 'pointer', background: 'linear-gradient(135deg, #10b981, #059669)', color: 'white', fontWeight: '600', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', boxShadow: '0 2px 8px rgba(16,185,129,0.3)'}}>
          <Download size={14}/>Подгрузить из прайса
        </button>
      )}
    </div>
  );
}
