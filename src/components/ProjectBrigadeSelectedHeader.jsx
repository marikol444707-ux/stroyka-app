import React, { useRef, useState } from 'react';
import { ArrowLeft, Check, Download, Eye, Upload } from 'lucide-react';
import { API } from '../api';
import { buildPerformerContractHtml } from '../utils/contractTemplates';

export default function ProjectBrigadeSelectedHeader({
  projectName,
  projectId,
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
  uploadPhoto,
  C,
  btnG,
  btnO,
  btnB,
}) {
  const contractFileRef = useRef(null);
  const [savingContract, setSavingContract] = useState(false);
  const [contractError, setContractError] = useState('');
  const closeContract = () => {
    setSelectedBrigadeContract(null);
    setBrigadeContractItems([]);
    setBrigadePayments([]);
  };

  const signContract = async (file) => {
    if (!file || typeof uploadPhoto !== 'function') return;
    setSavingContract(true);
    setContractError('');
    try {
      const scanUrl = await uploadPhoto(file, {projectId, projectName, context: 'brigade-contracts'});
      if (!scanUrl) throw new Error('Не удалось загрузить договор. Повторите попытку.');
      const response = await fetch(API + '/brigade-contracts/' + selectedBrigadeContract.id + '/signature', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({scanUrl}),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось сохранить договор.');
      const signedContract = {...selectedBrigadeContract, ...data};
      setSelectedBrigadeContract(signedContract);
      setBrigadeContracts(prev => prev.map(bc => bc.id === selectedBrigadeContract.id ? signedContract : bc));
    } catch (error) {
      setContractError(error.message || 'Не удалось сохранить договор.');
    } finally {
      setSavingContract(false);
      if (contractFileRef.current) contractFileRef.current.value = '';
    }
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
      kpp: profile?.kpp || '',
      ogrn: profile?.ogrn || st?.ogrnip || '',
      legalAddress: profile?.legalAddress || st?.address || '',
      bankBik: profile?.bankBik || st?.bankBik || '',
      bankCorr: profile?.bankCorr || st?.bankCorr || '',
      signatoryName: profile?.signatoryName || '',
      signatoryPosition: profile?.signatoryPosition || '',
      signatoryBasis: profile?.signatoryBasis || '',
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
    if (type.includes('ооо')) {
      if (!performer.kpp) missing.push('КПП');
      if (!performer.ogrn) missing.push('ОГРН');
      if (!performer.legalAddress) missing.push('юридический адрес');
      if (!performer.signatoryName) missing.push('ФИО подписанта');
      if (!performer.signatoryPosition) missing.push('должность подписанта');
      if (!performer.signatoryBasis) missing.push('основание полномочий');
    }
    if (!type.includes('труд') && !performer.bankAccount) missing.push('расчётный счёт');
    if (!type.includes('труд') && !performer.bankName) missing.push('банк');
    return missing;
  };

  const showContract = () => {
    const total = brigadeContractItems.reduce((sum, item) => sum + item.quantity * item.priceBrigade, 0);
    const frozen = selectedBrigadeContract.partySnapshot;
    const performer = frozen?.contractor ? {
      ...frozen.contractor,
      contractType: frozen.contractor.type,
      name: frozen.contractor.fullName,
    } : resolvePerformer();
    const missing = missingRequisites(performer);
    const html = (missing.length
      ? '<div style="border:1px solid #f59e0b;background:#fff7ed;padding:10px 12px;margin-bottom:12px;border-radius:8px;color:#92400e"><b>Внимание:</b> не хватает реквизитов: ' + missing.join(', ') + '. Заполните карточку исполнителя.</div>'
      : '') + buildPerformerContractHtml({
      company: frozen?.customer || (companyRequisites && companyRequisites.fullName ? companyRequisites : companyName),
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
    <div style={{padding: '14px', border: `1px solid ${C.border}`, borderRadius: '14px', marginBottom: '15px', background: C.card}}>
    <div style={{display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap'}}>
      <button onClick={closeContract} style={btnG}><ArrowLeft size={14}/>Назад</button>
      <b style={{color: C.text, fontSize: '14px'}}>{selectedBrigadeContract.brigadeName}</b>
      <span style={{padding: '3px 8px', borderRadius: '6px', fontSize: '11px', backgroundColor: C.accentLight, color: C.accent}}>
        {selectedBrigadeContract.contractorType}
      </span>
      {!selectedBrigadeContract.partySnapshot && (
        <>
          <input ref={contractFileRef} type="file" accept="image/*,.pdf" style={{display: 'none'}} onChange={e => signContract(e.target.files?.[0])}/>
          <button disabled={savingContract} onClick={() => contractFileRef.current?.click()} style={btnO}>
            <Upload size={14}/>{savingContract ? 'Сохраняем…' : selectedBrigadeContract.status === 'Подписан' ? 'Проверить подписанный договор' : 'Загрузить подписанный договор'}
          </button>
        </>
      )}
      {selectedBrigadeContract.partySnapshot && <span style={{fontSize: '12px', color: '#059669', display: 'flex', gap: 4, alignItems: 'center'}}><Check size={14}/>Стороны зафиксированы</span>}
      <button onClick={showContract} style={btnB}><Eye size={14}/>Договор</button>
      {selectedBrigadeContract.pricelistId && (
        <button onClick={loadFromPricelist} style={{border: 'none', borderRadius: '10px', padding: '8px 16px', cursor: 'pointer', background: 'linear-gradient(135deg, #10b981, #059669)', color: 'white', fontWeight: '600', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', boxShadow: '0 2px 8px rgba(16,185,129,0.3)'}}>
          <Download size={14}/>Подгрузить из прайса
        </button>
      )}
    </div>
    {contractError && <p role="alert" style={{color: '#dc2626', margin: '10px 0 0', fontSize: '12px'}}>{contractError}</p>}
    {selectedBrigadeContract.contractScanUrl && <p style={{color: C.textSec, margin: '10px 0 0', fontSize: '12px'}}>Подписанный оригинал сохранён в документах компании и используется во всех актах.</p>}
    </div>
  );
}
